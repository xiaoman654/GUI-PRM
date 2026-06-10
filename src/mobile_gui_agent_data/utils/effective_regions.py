from dataclasses import dataclass

from mobile_gui_agent_data.schemas import ActionType, GUIAction, ScreenSize, StepSample, UIElement
from mobile_gui_agent_data.utils.coordinates import bbox_to_pixel, point_to_pixel
from mobile_gui_agent_data.utils.ui_elements import valid_bbox


@dataclass(frozen=True)
class PixelBox:
    x1: float
    y1: float
    x2: float
    y2: float
    label: str = ""

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    def contains(self, point: tuple[float, float]) -> bool:
        x, y = point
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def to_list(self) -> list[float | str]:
        return [round(self.x1, 1), round(self.y1, 1), round(self.x2, 1), round(self.y2, 1), self.label]


@dataclass(frozen=True)
class EffectiveRegion:
    kind: str
    box: PixelBox
    source_element_index: int | None = None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def element_text(element: UIElement) -> str:
    return (element.text or "").strip().lower()


def element_label(element: UIElement) -> str:
    text = (element.text or "").strip()
    suffix = f":{text[:24]}" if text else ""
    return f"{element.index}:{element.ui_type}{suffix}"


def element_box(element: UIElement, screen_size: ScreenSize) -> PixelBox:
    box = bbox_to_pixel(element.bbox, screen_size)
    return PixelBox(box.x1, box.y1, box.x2, box.y2, element_label(element))


def expand_box(box: PixelBox, screen_size: ScreenSize, x_pad: float, y_pad: float, label: str | None = None) -> PixelBox:
    return PixelBox(
        clamp(box.x1 - x_pad, 0, screen_size.width),
        clamp(box.y1 - y_pad, 0, screen_size.height),
        clamp(box.x2 + x_pad, 0, screen_size.width),
        clamp(box.y2 + y_pad, 0, screen_size.height),
        label or box.label,
    )


def union_boxes(boxes: list[PixelBox], screen_size: ScreenSize, pad_x: float = 0, pad_y: float = 0, label: str = "") -> PixelBox:
    return expand_box(
        PixelBox(
            min(box.x1 for box in boxes),
            min(box.y1 for box in boxes),
            max(box.x2 for box in boxes),
            max(box.y2 for box in boxes),
            label,
        ),
        screen_size,
        pad_x,
        pad_y,
        label,
    )


def action_point_pixels(action: GUIAction, screen_size: ScreenSize) -> tuple[float, float] | None:
    point = action.primary_point()
    if point is None:
        return None
    return point_to_pixel(point, screen_size, action.coordinate_space)


def elements_containing_point(step: StepSample, point_px: tuple[float, float]) -> list[tuple[float, UIElement, PixelBox]]:
    if step.screen_size is None:
        return []
    matches = []
    for element in step.ui_elements:
        if not valid_bbox(element.bbox):
            continue
        box = element_box(element, step.screen_size)
        if box.contains(point_px):
            matches.append((box.area, element, box))
    matches.sort(key=lambda item: item[0])
    return matches


def smallest_element_containing_point(step: StepSample, point_px: tuple[float, float]) -> tuple[UIElement, PixelBox] | None:
    matches = elements_containing_point(step, point_px)
    if not matches:
        return None
    _area, element, box = matches[0]
    return element, box


def row_elements(step: StepSample, target_box: PixelBox, y_tolerance: float | None = None) -> list[tuple[UIElement, PixelBox]]:
    if step.screen_size is None:
        return []
    tolerance = y_tolerance if y_tolerance is not None else max(20, target_box.height * 1.5)
    row = []
    for element in step.ui_elements:
        if not valid_bbox(element.bbox):
            continue
        box = element_box(element, step.screen_size)
        center_close = abs(box.cy - target_box.cy) <= tolerance
        overlap = not (box.y2 < target_box.y1 or box.y1 > target_box.y2)
        if center_close or overlap:
            row.append((element, box))
    return row


def row_text(row: list[tuple[UIElement, PixelBox]]) -> str:
    return " ".join(element_text(element) for element, _box in sorted(row, key=lambda item: item[1].x1))


def is_search_like(element: UIElement, row: list[tuple[UIElement, PixelBox]]) -> bool:
    text = element_text(element)
    ui_type = (element.ui_type or "").upper()
    return "search" in text or ui_type == "ICON_MAGNIFYING_GLASS"


def search_related_boxes(
    row: list[tuple[UIElement, PixelBox]],
    target_box: PixelBox,
    screen_size: ScreenSize,
) -> list[PixelBox]:
    related = []
    max_gap = max(70, target_box.width * 2.5)
    for element, box in row:
        text = element_text(element)
        ui_type = (element.ui_type or "").upper()
        gap = max(0, max(box.x1 - target_box.x2, target_box.x1 - box.x2))
        searchish = "search" in text or ui_type in {
            "ICON_MAGNIFYING_GLASS",
            "ICON_MIC",
            "ICON_TAKE_PHOTO",
            "ICON_X",
        }
        if searchish and gap <= max_gap:
            related.append(box)
    if not related:
        related.append(target_box)
    # Keep search regions local to the input/suggestion area. Header rows often
    # also contain cart/share/menu icons, which must not be merged into search.
    return [box for box in related if abs(box.cy - target_box.cy) <= max(28, target_box.height * 2.0)]


def has_full_width_cta(row: list[tuple[UIElement, PixelBox]]) -> bool:
    text = row_text(row)
    phrases = [
        "sign in to check out",
        "buy it now",
        "buy now",
        "add to cart",
        "view in cart",
        "checkout",
    ]
    return any(phrase in text for phrase in phrases) or ("sign" in text and "check out" in text)


def is_compact_control(element: UIElement) -> bool:
    text = element_text(element)
    words = ["best match", "filter", "sort", "condition", "screen size", "maximum", "quantity"]
    return any(word in text for word in words)


def is_product_task(task: str) -> bool:
    task = task.lower()
    words = ["product", "item", "result", "cart", "macbook", "ebay", "amazon", "walmart", "bestbuy", "costco"]
    return any(word in task for word in words)


def horizontally_related(row: list[tuple[UIElement, PixelBox]], target_box: PixelBox, max_gap: float) -> list[PixelBox]:
    related = []
    for _element, box in sorted(row, key=lambda item: item[1].x1):
        gap = max(0, max(box.x1 - target_box.x2, target_box.x1 - box.x2))
        if gap <= max_gap:
            related.append(box)
    return related or [target_box]


def product_card_region(step: StepSample, target_box: PixelBox) -> PixelBox | None:
    if step.screen_size is None or not is_product_task(step.task):
        return None
    nearby = []
    for element in step.ui_elements:
        if not valid_bbox(element.bbox):
            continue
        box = element_box(element, step.screen_size)
        vertical_gap = max(0, max(box.y1 - target_box.y2, target_box.y1 - box.y2))
        center_dx = abs(box.cx - target_box.cx)
        same_column = center_dx <= max(150, target_box.width * 0.85)
        reasonable_vertical = vertical_gap <= max(110, target_box.height * 2.4)
        if same_column and reasonable_vertical:
            nearby.append(box)
    if len(nearby) < 2:
        return None
    return union_boxes(nearby, step.screen_size, pad_x=10, pad_y=10, label="product_card_region")


def build_effective_region_for_element(step: StepSample, element: UIElement, box: PixelBox) -> EffectiveRegion:
    if step.screen_size is None:
        return EffectiveRegion("raw_bbox", box, element.index)

    row = row_elements(step, box, max(20, box.height * 1.6))
    if is_search_like(element, row):
        row_boxes = [row_box for row_box in search_related_boxes(row, box, step.screen_size) if row_box.width > 2 and row_box.height > 2]
        row_union = union_boxes(row_boxes or [box], step.screen_size, pad_x=10, pad_y=max(8, box.height * 0.35), label="search_or_suggestion_row")
        region = PixelBox(
            max(0, row_union.x1 - 8),
            row_union.y1,
            min(step.screen_size.width, row_union.x2 + 8),
            row_union.y2,
            "search_or_suggestion_row",
        )
        return EffectiveRegion("search_or_suggestion_row", region, element.index)

    if has_full_width_cta(row):
        button_height = max(52, box.height * 2.7)
        region = PixelBox(
            step.screen_size.width * 0.04,
            clamp(box.cy - button_height / 2, 0, step.screen_size.height),
            step.screen_size.width * 0.96,
            clamp(box.cy + button_height / 2, 0, step.screen_size.height),
            "full_width_cta_button",
        )
        return EffectiveRegion("full_width_cta_button", region, element.index)

    if is_compact_control(element):
        related = horizontally_related(row, box, max_gap=max(48, box.width * 2.2))
        region = union_boxes(
            related,
            step.screen_size,
            pad_x=max(24, box.width * 0.35),
            pad_y=max(18, box.height * 0.95),
            label="compact_control_button",
        )
        return EffectiveRegion("compact_control_button", region, element.index)

    card = product_card_region(step, box)
    if card is not None:
        return EffectiveRegion("product_card_region", card, element.index)

    return EffectiveRegion(
        "padded_raw_bbox",
        expand_box(box, step.screen_size, max(6, box.width * 0.12), max(4, box.height * 0.12), "padded_raw_bbox"),
        element.index,
    )


def effective_region_for_point(step: StepSample, point_px: tuple[float, float]) -> EffectiveRegion | None:
    match = smallest_element_containing_point(step, point_px)
    if match is None:
        return None
    element, box = match
    return build_effective_region_for_element(step, element, box)


def action_effective_region(step: StepSample, action: GUIAction) -> EffectiveRegion | None:
    if action.type != ActionType.CLICK or step.screen_size is None:
        return None
    point = action_point_pixels(action, step.screen_size)
    if point is None:
        return None
    return effective_region_for_point(step, point)


def point_in_effective_region(action: GUIAction, step: StepSample, region: EffectiveRegion | None) -> bool:
    if region is None or step.screen_size is None:
        return False
    point = action_point_pixels(action, step.screen_size)
    return point is not None and region.box.contains(point)
