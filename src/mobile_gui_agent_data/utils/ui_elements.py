from mobile_gui_agent_data.schemas import BoundingBox, StepSample, UIElement
from mobile_gui_agent_data.utils.coordinates import bbox_to_pixel, point_to_pixel


def bbox_center(bbox: BoundingBox) -> tuple[float, float]:
    return (bbox.x1 + bbox.x2) / 2, (bbox.y1 + bbox.y2) / 2


def point_in_element(step: StepSample, point: tuple[float, float], element: UIElement, point_space: str) -> bool:
    if step.screen_size is None:
        return False
    x, y = point_to_pixel(point, step.screen_size, point_space)
    bbox = bbox_to_pixel(element.bbox, step.screen_size)
    return bbox.x1 <= x <= bbox.x2 and bbox.y1 <= y <= bbox.y2


def element_containing_action_point(step: StepSample) -> UIElement | None:
    point = step.action.primary_point()
    if point is None:
        return None
    for element in step.ui_elements:
        if point_in_element(step, point, element, step.action.coordinate_space):
            return element
    return None


def other_elements(step: StepSample, exclude: UIElement | None = None) -> list[UIElement]:
    if exclude is None:
        return step.ui_elements
    return [element for element in step.ui_elements if element.index != exclude.index]
