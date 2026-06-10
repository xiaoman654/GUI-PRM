import argparse
import html
import json
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from mobile_gui_agent_data.datasets.aitw import AITWParser
from mobile_gui_agent_data.schemas import ActionType, BoundingBox, ScreenSize, StepSample, UIElement
from mobile_gui_agent_data.utils.coordinates import bbox_to_pixel, point_to_pixel
from mobile_gui_agent_data.utils.ui_elements import valid_bbox


@dataclass
class PixelBox:
    x1: float
    y1: float
    x2: float
    y2: float

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


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def to_pixel_box(bbox: BoundingBox, screen_size: ScreenSize) -> PixelBox:
    box = bbox_to_pixel(bbox, screen_size)
    return PixelBox(box.x1, box.y1, box.x2, box.y2)


def expand_box(box: PixelBox, screen_size: ScreenSize, x_pad: float, y_pad: float) -> PixelBox:
    return PixelBox(
        clamp(box.x1 - x_pad, 0, screen_size.width),
        clamp(box.y1 - y_pad, 0, screen_size.height),
        clamp(box.x2 + x_pad, 0, screen_size.width),
        clamp(box.y2 + y_pad, 0, screen_size.height),
    )


def union_boxes(boxes: list[PixelBox], screen_size: ScreenSize, pad_x: float = 0, pad_y: float = 0) -> PixelBox:
    x1 = min(box.x1 for box in boxes)
    y1 = min(box.y1 for box in boxes)
    x2 = max(box.x2 for box in boxes)
    y2 = max(box.y2 for box in boxes)
    return expand_box(PixelBox(x1, y1, x2, y2), screen_size, pad_x, pad_y)


def normalized_image_path(path: str | None, root: Path) -> Path | None:
    if not path:
        return None
    p = Path(path)
    if p.is_absolute():
        return p
    return root / p


def infer_screen_size(step: StepSample, image_path: Path) -> ScreenSize:
    if step.screen_size is not None:
        return step.screen_size
    with Image.open(image_path) as image:
        width, height = image.size
    return ScreenSize(width=width, height=height)


def element_box(element: UIElement, screen_size: ScreenSize) -> PixelBox:
    return to_pixel_box(element.bbox, screen_size)


def find_target_element(step: StepSample, screen_size: ScreenSize) -> UIElement | None:
    point = step.action.primary_point()
    if point is None:
        return None
    pixel_point = point_to_pixel(point, screen_size, step.action.coordinate_space)
    candidates = []
    for element in step.ui_elements:
        if not valid_bbox(element.bbox):
            continue
        box = element_box(element, screen_size)
        if box.contains(pixel_point):
            candidates.append((box.area, element))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def same_row_elements(
    target_box: PixelBox,
    step: StepSample,
    screen_size: ScreenSize,
    y_tolerance: float,
) -> list[tuple[UIElement, PixelBox]]:
    row = []
    for element in step.ui_elements:
        if not valid_bbox(element.bbox):
            continue
        box = element_box(element, screen_size)
        center_close = abs(box.cy - target_box.cy) <= y_tolerance
        overlap = not (box.y2 < target_box.y1 or box.y1 > target_box.y2)
        if center_close or overlap:
            row.append((element, box))
    return row


def classify_region(target: UIElement, target_box: PixelBox, step: StepSample, screen_size: ScreenSize) -> str:
    text = (target.text or "").lower()
    ui_type = (target.ui_type or "").upper()
    task = step.task.lower()
    row = same_row_elements(target_box, step, screen_size, max(20, target_box.height * 1.4))
    row_types = {element.ui_type.upper() for element, _box in row}

    if (
        "search" in text
        or "search" in task and target_box.y1 < screen_size.height * 0.35
        or "ICON_MAGNIFYING_GLASS" in row_types
    ):
        return "search_or_suggestion_row"

    button_words = [
        "add to cart",
        "buy",
        "continue",
        "accept",
        "verify",
        "submit",
        "next",
        "done",
        "sign in",
        "yes",
        "no thanks",
        "save",
    ]
    if any(word in text for word in button_words):
        return "button_like"

    product_words = ["product", "item", "result", "cart", "macbook", "ebay", "amazon", "walmart", "bestbuy", "costco"]
    if any(word in task for word in product_words) and (ui_type == "TEXT" or target_box.height > 60):
        return "possible_card_region"

    return "padded_bbox"


def build_effective_region(
    target: UIElement,
    step: StepSample,
    screen_size: ScreenSize,
) -> tuple[str, PixelBox]:
    target_box = element_box(target, screen_size)
    kind = classify_region(target, target_box, step, screen_size)

    if kind == "search_or_suggestion_row":
        row = same_row_elements(target_box, step, screen_size, max(24, target_box.height * 1.6))
        row_boxes = [box for _element, box in row if box.width > 2 and box.height > 2]
        if row_boxes:
            row_union = union_boxes(row_boxes, screen_size, pad_x=12, pad_y=max(8, target_box.height * 0.4))
            return kind, PixelBox(
                clamp(min(row_union.x1, 0), 0, screen_size.width),
                row_union.y1,
                clamp(max(row_union.x2, screen_size.width * 0.75), 0, screen_size.width),
                row_union.y2,
            )
        return kind, expand_box(target_box, screen_size, target_box.width * 3.0, target_box.height * 0.7)

    if kind == "button_like":
        return kind, expand_box(
            target_box,
            screen_size,
            max(24, target_box.width * 0.55),
            max(10, target_box.height * 0.65),
        )

    if kind == "possible_card_region":
        nearby = []
        for element in step.ui_elements:
            if not valid_bbox(element.bbox):
                continue
            box = element_box(element, screen_size)
            vertical_gap = max(0, max(box.y1 - target_box.y2, target_box.y1 - box.y2))
            horizontal_overlap = min(box.x2, target_box.x2) - max(box.x1, target_box.x1)
            same_column = horizontal_overlap > -screen_size.width * 0.20
            if vertical_gap <= max(120, target_box.height * 3.0) and same_column:
                nearby.append(box)
        if nearby:
            return kind, union_boxes(nearby, screen_size, pad_x=12, pad_y=12)

    return kind, expand_box(
        target_box,
        screen_size,
        max(12, target_box.width * 0.35),
        max(8, target_box.height * 0.35),
    )


def draw_box(draw: ImageDraw.ImageDraw, box: PixelBox, color: str, width: int = 3) -> None:
    draw.rectangle([box.x1, box.y1, box.x2, box.y2], outline=color, width=width)


def draw_point(draw: ImageDraw.ImageDraw, point: tuple[float, float], color: str) -> None:
    x, y = point
    r = 8
    draw.ellipse([x - r, y - r, x + r, y + r], fill=color, outline="white", width=2)


def draw_label(draw: ImageDraw.ImageDraw, text: str, xy: tuple[float, float], fill: str) -> None:
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    x, y = xy
    bbox = draw.textbbox((x, y), text, font=font)
    draw.rectangle([bbox[0] - 3, bbox[1] - 2, bbox[2] + 3, bbox[3] + 2], fill="white")
    draw.text((x, y), text, fill=fill, font=font)


def render_sample(
    step: StepSample,
    image_path: Path,
    output_path: Path,
    index: int,
    draw_all_raw: bool,
) -> dict | None:
    screen_size = infer_screen_size(step, image_path)
    target = find_target_element(step, screen_size)
    if target is None:
        return None

    target_box = element_box(target, screen_size)
    region_type, effective_box = build_effective_region(target, step, screen_size)
    point = step.action.primary_point()
    pixel_point = point_to_pixel(point, screen_size, step.action.coordinate_space) if point else None

    with Image.open(image_path).convert("RGB") as image:
        draw = ImageDraw.Draw(image, "RGBA")
        if draw_all_raw:
            for element in step.ui_elements:
                if valid_bbox(element.bbox):
                    draw_box(draw, element_box(element, screen_size), (120, 120, 120, 85), width=1)
        draw_box(draw, effective_box, (255, 149, 0, 255), width=4)
        draw_box(draw, target_box, (0, 122, 255, 255), width=4)
        if pixel_point:
            draw_point(draw, pixel_point, (255, 59, 48, 255))
        draw_label(draw, f"raw bbox #{target.index}", (8, 8), "blue")
        draw_label(draw, f"effective: {region_type}", (8, 30), "darkorange")
        image.save(output_path)

    return {
        "index": index,
        "output": str(output_path),
        "image": str(image_path),
        "episode_id": step.episode_id,
        "step_id": step.step_id,
        "task": step.task,
        "action_type": step.action.type.value,
        "target_index": target.index,
        "target_text": target.text,
        "target_ui_type": target.ui_type,
        "region_type": region_type,
        "raw_bbox": [round(target_box.x1, 1), round(target_box.y1, 1), round(target_box.x2, 1), round(target_box.y2, 1)],
        "effective_region": [
            round(effective_box.x1, 1),
            round(effective_box.y1, 1),
            round(effective_box.x2, 1),
            round(effective_box.y2, 1),
        ],
    }


def write_html(records: list[dict], output_html: Path, image_dir: Path) -> None:
    cards = []
    for record in records:
        rel = Path(record["output"]).relative_to(output_html.parent).as_posix()
        cards.append(
            f"""
            <article class="card">
              <h2>#{record['index']} {html.escape(record['region_type'])}</h2>
              <img src="{html.escape(rel)}" />
              <p><b>task:</b> {html.escape(record['task'])}</p>
              <p><b>target:</b> #{record['target_index']} {html.escape(record['target_ui_type'])} {html.escape(record['target_text'])}</p>
              <p><b>raw:</b> {html.escape(str(record['raw_bbox']))}</p>
              <p><b>effective:</b> {html.escape(str(record['effective_region']))}</p>
            </article>
            """
        )
    output_html.write_text(
        f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Effective Region Samples</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f6f7f9; }}
    header {{ padding: 18px 22px; background: white; border-bottom: 1px solid #ddd; position: sticky; top: 0; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 16px; padding: 16px; }}
    .card {{ background: white; border: 1px solid #d8dde6; border-radius: 8px; padding: 12px; }}
    .card img {{ width: 100%; height: auto; border: 1px solid #eee; }}
    h1 {{ margin: 0 0 8px; font-size: 20px; }}
    h2 {{ margin: 0 0 8px; font-size: 16px; }}
    p {{ font-size: 13px; line-height: 1.35; }}
    .legend span {{ display: inline-block; margin-right: 16px; }}
  </style>
</head>
<body>
  <header>
    <h1>Effective Click Region Samples</h1>
    <div class="legend">
      <span style="color:#007aff">blue = raw target bbox</span>
      <span style="color:#ff9500">orange = estimated effective region</span>
      <span style="color:#ff3b30">red dot = GT click</span>
      <span style="color:#777">gray = all raw UI bboxes</span>
    </div>
  </header>
  <main>
    {''.join(cards)}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def load_steps(input_path: Path) -> list[StepSample]:
    parser = AITWParser()
    steps = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw = json.loads(line)
            steps.extend(parser.parse(raw))
    return steps


def main() -> None:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--input", default="data/raw/aitw_single/unseen_subject_train_1000_with_images.jsonl")
    arg_parser.add_argument("--output-dir", default="reports/effective_regions")
    arg_parser.add_argument("--limit", type=int, default=40)
    arg_parser.add_argument("--seed", type=int, default=7)
    arg_parser.add_argument("--image-root", default=".")
    arg_parser.add_argument("--draw-all-raw", action="store_true")
    args = arg_parser.parse_args()

    root = Path(args.image_root)
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    steps = [
        step
        for step in load_steps(input_path)
        if step.action.type == ActionType.CLICK and step.screenshot_before
    ]
    random.Random(args.seed).shuffle(steps)

    records = []
    for step in steps:
        image_path = normalized_image_path(step.screenshot_before, root)
        if image_path is None or not image_path.exists():
            continue
        output_path = image_dir / f"{len(records):04d}_effective_region.png"
        record = render_sample(step, image_path, output_path, len(records), args.draw_all_raw)
        if record is not None:
            records.append(record)
        if len(records) >= args.limit:
            break

    metadata_path = output_dir / "effective_region_samples.json"
    html_path = output_dir / "effective_region_samples.html"
    metadata_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    write_html(records, html_path, image_dir)

    print(
        json.dumps(
            {
                "input": str(input_path),
                "num_samples": len(records),
                "html": str(html_path),
                "metadata": str(metadata_path),
                "image_dir": str(image_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
