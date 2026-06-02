import random

from mobile_gui_agent_data.schemas import ActionType, GUIAction, StepSample
from mobile_gui_agent_data.utils.coordinates import point_from_pixel, point_to_pixel
from mobile_gui_agent_data.utils.ui_elements import (
    bbox_center,
    element_containing_action_point,
    other_elements,
)


def random_point_for_step(step: StepSample) -> tuple[float, float]:
    if step.screen_size is None:
        return 0.0, 0.0

    pixel_point = (
        random.uniform(0, step.screen_size.width - 1),
        random.uniform(0, step.screen_size.height - 1),
    )
    return point_from_pixel(pixel_point, step.screen_size, step.action.coordinate_space)


def random_coordinate_negative(step: StepSample) -> GUIAction:
    return GUIAction(
        type=ActionType.CLICK,
        point=random_point_for_step(step),
        coordinate_space=step.action.coordinate_space,
    )


def shifted_coordinate_negative(step: StepSample, offset_px: float = 120.0) -> GUIAction:
    point = step.action.primary_point()
    if point is None or step.screen_size is None:
        return random_coordinate_negative(step)

    x, y = point_to_pixel(point, step.screen_size, step.action.coordinate_space)
    source_element = element_containing_action_point(step)
    for dx, dy in [
        (offset_px, 0),
        (-offset_px, 0),
        (0, offset_px),
        (0, -offset_px),
        (offset_px, offset_px),
        (-offset_px, -offset_px),
    ]:
        shifted = (x + dx, y + dy)
        shifted_in_action_space = point_from_pixel(shifted, step.screen_size, step.action.coordinate_space)
        shifted_step = step.model_copy(
            update={"action": step.action.model_copy(update={"point": shifted_in_action_space})}
        )
        if element_containing_action_point(shifted_step) != source_element:
            return step.action.model_copy(update={"point": shifted_in_action_space})

    shifted = (x + offset_px, y + offset_px)
    shifted_in_action_space = point_from_pixel(shifted, step.screen_size, step.action.coordinate_space)
    return step.action.model_copy(update={"point": shifted_in_action_space})


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
    return GUIAction(**payload)


NEGATIVE_SAMPLERS = {
    "random_coordinate": random_coordinate_negative,
    "same_screen_element": same_screen_element_negative,
    "shifted_coordinate": shifted_coordinate_negative,
    "wrong_action_type": wrong_action_type_negative,
}
