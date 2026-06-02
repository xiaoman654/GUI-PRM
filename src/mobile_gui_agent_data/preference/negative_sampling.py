import random

from mobile_gui_agent_data.schemas import ActionType, GUIAction, StepSample
from mobile_gui_agent_data.utils.coordinates import point_from_pixel, point_to_pixel
from mobile_gui_agent_data.utils.ui_elements import (
    bbox_center,
    element_containing_action_point,
    element_containing_point,
    other_elements,
)


def clamp_pixel_point(step: StepSample, point: tuple[float, float]) -> tuple[float, float]:
    if step.screen_size is None:
        return point
    x, y = point
    return (
        max(0.0, min(float(step.screen_size.width - 1), x)),
        max(0.0, min(float(step.screen_size.height - 1), y)),
    )


def action_with_metadata(action: GUIAction, **metadata: object) -> GUIAction:
    return action.model_copy(update={"metadata": {**action.metadata, **metadata}})


def random_point_for_step(step: StepSample, avoid_ui: bool = False) -> tuple[float, float]:
    if step.screen_size is None:
        return 0.0, 0.0

    fallback = (0.0, 0.0)
    for _ in range(50 if avoid_ui else 1):
        pixel_point = (
            random.uniform(0, step.screen_size.width - 1),
            random.uniform(0, step.screen_size.height - 1),
        )
        action_point = point_from_pixel(pixel_point, step.screen_size, step.action.coordinate_space)
        fallback = action_point
        if not avoid_ui or element_containing_point(step, action_point, step.action.coordinate_space) is None:
            return action_point
    return fallback


def random_coordinate_negative(step: StepSample) -> GUIAction:
    point = random_point_for_step(step, avoid_ui=True)
    negative_subtype = (
        "random_non_ui_point"
        if element_containing_point(step, point, step.action.coordinate_space) is None
        else "random_coordinate"
    )
    return GUIAction(
        type=ActionType.CLICK,
        point=point,
        coordinate_space=step.action.coordinate_space,
        metadata={"negative_source": "random_coordinate", "negative_subtype": negative_subtype},
    )


def wrong_swipe_direction_negative(step: StepSample) -> GUIAction:
    if step.action.start_point is None or step.action.end_point is None:
        return random_coordinate_negative(step)
    return step.action.model_copy(
        update={
            "point": step.action.end_point,
            "start_point": step.action.end_point,
            "end_point": step.action.start_point,
            "metadata": {
                **step.action.metadata,
                "negative_source": "shifted_coordinate",
                "negative_subtype": "wrong_swipe_direction",
            },
        }
    )


def shifted_coordinate_negative(step: StepSample, offset_px: float = 120.0) -> GUIAction:
    if step.action.type in {ActionType.SWIPE, ActionType.SCROLL}:
        return wrong_swipe_direction_negative(step)

    point = step.action.primary_point()
    if point is None or step.screen_size is None:
        return random_coordinate_negative(step)

    x, y = point_to_pixel(point, step.screen_size, step.action.coordinate_space)
    source_element = element_containing_action_point(step)
    directions = [
        (1, 0),
        (-1, 0),
        (0, 1),
        (0, -1),
        (1, 1),
        (-1, -1),
        (1, -1),
        (-1, 1),
    ]
    candidates = []
    for radius in [offset_px, offset_px * 1.5, offset_px * 2.0]:
        for dx, dy in directions:
            candidates.append((dx * radius, dy * radius))

    fallback_action = None
    for dx, dy in candidates:
        shifted = clamp_pixel_point(step, (x + dx, y + dy))
        shifted_in_action_space = point_from_pixel(shifted, step.screen_size, step.action.coordinate_space)
        candidate_element = element_containing_point(step, shifted_in_action_space, step.action.coordinate_space)
        if candidate_element != source_element and fallback_action is None:
            fallback_action = step.action.model_copy(
                update={
                    "point": shifted_in_action_space,
                    "metadata": {
                        **step.action.metadata,
                        "negative_source": "shifted_coordinate",
                        "negative_subtype": "shifted_other_ui_element" if candidate_element else "near_miss_non_ui_shift",
                    },
                }
            )
        if candidate_element is None:
            return step.action.model_copy(
                update={
                    "point": shifted_in_action_space,
                    "metadata": {
                        **step.action.metadata,
                        "negative_source": "shifted_coordinate",
                        "negative_subtype": "near_miss_non_ui_shift",
                    },
                }
            )

    if fallback_action is not None:
        return fallback_action

    shifted = clamp_pixel_point(step, (x + offset_px, y + offset_px))
    shifted_in_action_space = point_from_pixel(shifted, step.screen_size, step.action.coordinate_space)
    return step.action.model_copy(
        update={
            "point": shifted_in_action_space,
            "metadata": {
                **step.action.metadata,
                "negative_source": "shifted_coordinate",
                "negative_subtype": "shifted_coordinate_fallback",
            },
        }
    )


def same_screen_element_negative(step: StepSample) -> GUIAction:
    if step.screen_size is None or not step.ui_elements:
        return random_coordinate_negative(step)

    source_element = element_containing_action_point(step)
    candidates = other_elements(step, exclude=source_element)
    if not candidates:
        return random_coordinate_negative(step)

    element = random.choice(candidates)
    center = bbox_center(element.bbox)
    point = point_from_pixel(
        point_to_pixel(center, step.screen_size, element.bbox.coordinate_space),
        step.screen_size,
        step.action.coordinate_space,
    )
    return GUIAction(
        type=ActionType.CLICK,
        point=point,
        coordinate_space=step.action.coordinate_space,
        metadata={
            "negative_source": "same_screen_element",
            "negative_subtype": "wrong_ui_element",
            "ui_element_index": element.index,
            "ui_element_text": element.text,
            "ui_element_type": element.ui_type,
        },
    )


def wrong_action_type_negative(step: StepSample) -> GUIAction:
    replacement = ActionType.TYPE if step.action.type == ActionType.CLICK else ActionType.CLICK
    payload = {"type": replacement}
    if replacement == ActionType.TYPE:
        payload["text"] = ""
    else:
        payload["point"] = step.action.primary_point() or (0.0, 0.0)
        payload["coordinate_space"] = step.action.coordinate_space
    action = GUIAction(**payload)
    return action_with_metadata(
        action,
        negative_source="wrong_action_type",
        negative_subtype=f"{step.action.type.value}_to_{replacement.value}",
    )


NEGATIVE_SAMPLERS = {
    "random_coordinate": random_coordinate_negative,
    "same_screen_element": same_screen_element_negative,
    "shifted_coordinate": shifted_coordinate_negative,
    "wrong_action_type": wrong_action_type_negative,
}
