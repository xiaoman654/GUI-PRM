from mobile_gui_agent_data.schemas import BoundingBox, GUIAction, ScreenSize


def point_to_pixel(
    point: tuple[float, float],
    screen_size: ScreenSize,
    coordinate_space: str = "pixel",
) -> tuple[float, float]:
    x, y = point
    if coordinate_space == "pixel":
        return x, y
    if coordinate_space == "normalized_1000":
        return x / 1000.0 * screen_size.width, y / 1000.0 * screen_size.height
    if coordinate_space == "normalized_1":
        return x * screen_size.width, y * screen_size.height
    raise ValueError(f"Unsupported coordinate space: {coordinate_space}")


def point_from_pixel(
    point: tuple[float, float],
    screen_size: ScreenSize,
    coordinate_space: str = "normalized_1000",
) -> tuple[float, float]:
    x, y = point
    if coordinate_space == "pixel":
        return x, y
    if coordinate_space == "normalized_1000":
        return x / screen_size.width * 1000.0, y / screen_size.height * 1000.0
    if coordinate_space == "normalized_1":
        return x / screen_size.width, y / screen_size.height
    raise ValueError(f"Unsupported coordinate space: {coordinate_space}")


def action_to_coordinate_space(
    action: GUIAction,
    screen_size: ScreenSize,
    coordinate_space: str = "normalized_1000",
) -> GUIAction:
    updates = {"coordinate_space": coordinate_space}
    if action.point is not None:
        pixel_point = point_to_pixel(action.point, screen_size, action.coordinate_space)
        updates["point"] = point_from_pixel(pixel_point, screen_size, coordinate_space)
    if action.start_point is not None:
        pixel_point = point_to_pixel(action.start_point, screen_size, action.coordinate_space)
        updates["start_point"] = point_from_pixel(pixel_point, screen_size, coordinate_space)
    if action.end_point is not None:
        pixel_point = point_to_pixel(action.end_point, screen_size, action.coordinate_space)
        updates["end_point"] = point_from_pixel(pixel_point, screen_size, coordinate_space)
    return action.model_copy(update=updates)


def bbox_from_pixel(
    bbox: BoundingBox,
    screen_size: ScreenSize,
    coordinate_space: str = "normalized_1000",
) -> BoundingBox:
    if coordinate_space == "pixel":
        return bbox.model_copy(update={"coordinate_space": "pixel"})
    x1, y1 = point_from_pixel((bbox.x1, bbox.y1), screen_size, coordinate_space)
    x2, y2 = point_from_pixel((bbox.x2, bbox.y2), screen_size, coordinate_space)
    return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, coordinate_space=coordinate_space)


def bbox_to_coordinate_space(
    bbox: BoundingBox,
    screen_size: ScreenSize,
    coordinate_space: str = "normalized_1000",
) -> BoundingBox:
    pixel_bbox = bbox_to_pixel(bbox, screen_size)
    return bbox_from_pixel(pixel_bbox, screen_size, coordinate_space)


def bbox_to_pixel(bbox: BoundingBox, screen_size: ScreenSize) -> BoundingBox:
    if bbox.coordinate_space == "pixel":
        return bbox
    x1, y1 = point_to_pixel((bbox.x1, bbox.y1), screen_size, bbox.coordinate_space)
    x2, y2 = point_to_pixel((bbox.x2, bbox.y2), screen_size, bbox.coordinate_space)
    return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, coordinate_space="pixel")
