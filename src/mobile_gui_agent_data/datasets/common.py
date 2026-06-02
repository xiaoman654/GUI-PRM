import re
from collections.abc import Iterable
from typing import Any

from mobile_gui_agent_data.schemas import ActionType, BoundingBox, GUIAction, ScreenSize, UIElement


ACTION_PATTERN = re.compile(r"(?P<name>[a-zA-Z_ ]+)\s*\((?P<args>.*)\)")
AITW_SWIPE_DISTANCE_THRESHOLD = 0.04


def first_present(payload: dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return default


def parse_screen_size(payload: dict[str, Any]) -> ScreenSize | None:
    screen = first_present(payload, ["screen_size", "image_size", "resolution", "size"])
    if isinstance(screen, dict):
        width = first_present(screen, ["width", "w", "screen_width", "image_width"])
        height = first_present(screen, ["height", "h", "screen_height", "image_height"])
        if width is not None and height is not None:
            return ScreenSize(width=int(width), height=int(height))
    if isinstance(screen, (list, tuple)) and len(screen) == 2:
        return ScreenSize(width=int(screen[0]), height=int(screen[1]))

    width = first_present(payload, ["screen_width", "image_width", "width", "w"])
    height = first_present(payload, ["screen_height", "image_height", "height", "h"])
    if width is not None and height is not None:
        return ScreenSize(width=int(width), height=int(height))

    image_encoded = payload.get("image_encoded")
    if isinstance(image_encoded, dict):
        size = image_encoded.get("size")
        if isinstance(size, (list, tuple)) and len(size) == 2:
            return ScreenSize(width=int(size[0]), height=int(size[1]))
    return None


def parse_point(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        x = first_present(value, ["x", "X", "left"])
        y = first_present(value, ["y", "Y", "top"])
        if x is not None and y is not None:
            return float(x), float(y)
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return float(value[0]), float(value[1])
    return None


def normalize_action_type(raw_type: Any) -> ActionType:
    text = str(raw_type or "").strip().lower().replace(" ", "_")
    aliases = {
        "tap": ActionType.CLICK,
        "click": ActionType.CLICK,
        "touch": ActionType.CLICK,
        "input_text": ActionType.TYPE,
        "type_text": ActionType.TYPE,
        "type": ActionType.TYPE,
        "text": ActionType.TYPE,
        "scroll": ActionType.SCROLL,
        "swipe": ActionType.SWIPE,
        "press_back": ActionType.BACK,
        "back": ActionType.BACK,
        "press_home": ActionType.HOME,
        "home": ActionType.HOME,
        "wait": ActionType.WAIT,
        "done": ActionType.FINISH,
        "finish": ActionType.FINISH,
        "task_complete": ActionType.FINISH,
        "task_impossible": ActionType.IMPOSSIBLE,
        "impossible": ActionType.IMPOSSIBLE,
    }
    return aliases.get(text, ActionType.WAIT)


def parse_yx_point(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    y, x = value[:2]
    return float(x), float(y)


def is_aitw_tap(touch_xy: tuple[float, float], lift_xy: tuple[float, float]) -> bool:
    dx = touch_xy[0] - lift_xy[0]
    dy = touch_xy[1] - lift_xy[1]
    return (dx**2 + dy**2) ** 0.5 <= AITW_SWIPE_DISTANCE_THRESHOLD


def parse_aitw_action(raw_step: dict[str, Any]) -> GUIAction | None:
    raw_type = raw_step.get("results_action_type")
    if raw_type is None:
        return None

    action_type = int(raw_type)
    typed_text = first_present(raw_step, ["results_type_action", "type_action"], "")
    if isinstance(typed_text, list):
        typed_text = typed_text[0] if typed_text else ""

    touch = parse_yx_point(raw_step.get("results_yx_touch"))
    lift = parse_yx_point(raw_step.get("results_yx_lift"))
    metadata = {"aitw_action_type": action_type}

    if action_type == 3:
        return GUIAction(type=ActionType.TYPE, text=str(typed_text), metadata=metadata)
    if action_type == 4:
        if touch is None:
            return GUIAction(type=ActionType.WAIT, metadata=metadata)
        if lift is None or is_aitw_tap(touch, lift):
            return GUIAction(
                type=ActionType.CLICK,
                point=touch,
                coordinate_space="normalized_1",
                metadata=metadata,
            )
        return GUIAction(
            type=ActionType.SWIPE,
            start_point=touch,
            end_point=lift,
            coordinate_space="normalized_1",
            metadata=metadata,
        )
    if action_type == 5:
        return GUIAction(type=ActionType.BACK, metadata=metadata)
    if action_type == 6:
        return GUIAction(type=ActionType.HOME, metadata=metadata)
    if action_type == 7:
        return GUIAction(type=ActionType.WAIT, metadata={**metadata, "semantic": "press_enter"})
    if action_type == 10:
        return GUIAction(type=ActionType.FINISH, metadata=metadata)
    if action_type == 11:
        return GUIAction(type=ActionType.IMPOSSIBLE, metadata=metadata)
    return GUIAction(type=ActionType.WAIT, metadata=metadata)


def parse_string_action(raw_action: str) -> GUIAction:
    text = raw_action.strip()
    match = ACTION_PATTERN.match(text)
    if not match:
        return GUIAction(type=normalize_action_type(text), metadata={"raw_action": raw_action})

    action_type = normalize_action_type(match.group("name"))
    args = [item.strip().strip("'\"") for item in match.group("args").split(",") if item.strip()]
    if action_type == ActionType.CLICK and len(args) >= 2:
        return GUIAction(type=action_type, point=(float(args[0]), float(args[1])), metadata={"raw_action": raw_action})
    if action_type == ActionType.TYPE:
        return GUIAction(type=action_type, text=", ".join(args), metadata={"raw_action": raw_action})
    if action_type in {ActionType.SCROLL, ActionType.SWIPE} and args:
        return GUIAction(type=action_type, direction=args[0], metadata={"raw_action": raw_action})
    return GUIAction(type=action_type, metadata={"raw_action": raw_action})


def parse_action(raw_action: Any) -> GUIAction:
    if isinstance(raw_action, GUIAction):
        return raw_action
    if isinstance(raw_action, str):
        return parse_string_action(raw_action)
    if not isinstance(raw_action, dict):
        return GUIAction(type=ActionType.WAIT, metadata={"raw_action": raw_action})

    action_type = normalize_action_type(first_present(raw_action, ["type", "action_type", "action", "name"]))
    point = parse_point(first_present(raw_action, ["point", "position", "coordinate", "coords"]))
    if point is None:
        x = first_present(raw_action, ["x", "touch_x", "tap_x"])
        y = first_present(raw_action, ["y", "touch_y", "tap_y"])
        if x is not None and y is not None:
            point = (float(x), float(y))

    return GUIAction(
        type=action_type,
        point=point,
        start_point=parse_point(first_present(raw_action, ["start_point", "start", "from"])),
        end_point=parse_point(first_present(raw_action, ["end_point", "end", "to"])),
        text=first_present(raw_action, ["text", "typed_text", "input_text", "value"]),
        direction=first_present(raw_action, ["direction", "scroll_direction", "swipe_direction"]),
        coordinate_space=first_present(raw_action, ["coordinate_space", "coord_space"], "pixel"),
        metadata={"raw_action": raw_action},
    )


def parse_bbox(raw_bbox: Any) -> BoundingBox | None:
    if raw_bbox is None:
        return None
    if isinstance(raw_bbox, dict):
        if all(key in raw_bbox for key in ["x1", "y1", "x2", "y2"]):
            return BoundingBox(
                x1=float(raw_bbox["x1"]),
                y1=float(raw_bbox["y1"]),
                x2=float(raw_bbox["x2"]),
                y2=float(raw_bbox["y2"]),
                coordinate_space=raw_bbox.get("coordinate_space", "pixel"),
            )
        if all(key in raw_bbox for key in ["left", "top", "right", "bottom"]):
            return BoundingBox(
                x1=float(raw_bbox["left"]),
                y1=float(raw_bbox["top"]),
                x2=float(raw_bbox["right"]),
                y2=float(raw_bbox["bottom"]),
                coordinate_space=raw_bbox.get("coordinate_space", "pixel"),
            )
    if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) >= 4:
        return BoundingBox(
            x1=float(raw_bbox[0]),
            y1=float(raw_bbox[1]),
            x2=float(raw_bbox[2]),
            y2=float(raw_bbox[3]),
        )
    return None


def parse_aitw_ui_elements(raw_step: dict[str, Any]) -> list[UIElement]:
    positions = raw_step.get("image_ui_annotations_positions") or []
    texts = raw_step.get("image_ui_annotations_text") or []
    ui_types = raw_step.get("image_ui_annotations_ui_types") or []
    if not isinstance(positions, list) or len(positions) < 4:
        return []

    num_elements = min(len(positions) // 4, len(texts), len(ui_types))
    elements = []
    for idx in range(num_elements):
        y_center, x_center, height, width = [float(value) for value in positions[idx * 4 : (idx + 1) * 4]]
        x1 = max(0.0, x_center - width / 2)
        y1 = max(0.0, y_center - height / 2)
        x2 = min(1.0, x_center + width / 2)
        y2 = min(1.0, y_center + height / 2)
        elements.append(
            UIElement(
                index=idx,
                text=str(texts[idx] or ""),
                ui_type=str(ui_types[idx] or ""),
                bbox=BoundingBox(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    coordinate_space="normalized_1",
                ),
            )
        )
    return elements


def get_episode_steps(raw_episode: dict[str, Any]) -> list[dict[str, Any]]:
    steps = first_present(raw_episode, ["steps", "actions", "trajectory", "events"], [])
    if isinstance(steps, list) and steps:
        return steps
    if "results_action_type" in raw_episode:
        return [raw_episode]
    if isinstance(steps, list):
        return steps
    return []


def get_screenshot_before(raw_step: dict[str, Any]) -> str | None:
    value = first_present(
        raw_step,
        ["screenshot_before", "image", "image_path", "screenshot", "before", "image_encoded"],
    )
    if isinstance(value, dict) and isinstance(value.get("path"), str):
        return value["path"]
    return value if isinstance(value, str) else None


def get_screenshot_after(raw_step: dict[str, Any]) -> str | None:
    return first_present(raw_step, ["screenshot_after", "next_image", "next_image_path", "after"])
