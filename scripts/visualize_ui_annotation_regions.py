import argparse
import html
import json
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class Box:
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
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    def valid(self) -> bool:
        return self.x2 > self.x1 and self.y2 > self.y1


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def expand(box: Box, width: int, height: int, x_pad: float, y_pad: float, label: str) -> Box:
    return Box(
        clamp(box.x1 - x_pad, 0, width),
        clamp(box.y1 - y_pad, 0, height),
        clamp(box.x2 + x_pad, 0, width),
        clamp(box.y2 + y_pad, 0, height),
        label=label,
    )


def union(boxes: list[Box], width: int, height: int, pad_x: float, pad_y: float, label: str) -> Box:
    return expand(
        Box(
            min(box.x1 for box in boxes),
            min(box.y1 for box in boxes),
            max(box.x2 for box in boxes),
            max(box.y2 for box in boxes),
        ),
        width,
        height,
        pad_x,
        pad_y,
        label,
    )


def raw_boxes(record: dict, width: int, height: int) -> list[Box]:
    positions = record.get("image_ui_annotations_positions") or []
    texts = record.get("image_ui_annotations_text") or []
    ui_types = record.get("image_ui_annotations_ui_types") or []
    num_elements = min(len(positions) // 4, len(texts), len(ui_types))
    boxes = []
    for idx in range(num_elements):
        y_center, x_center, box_h, box_w = [float(value) for value in positions[idx * 4 : (idx + 1) * 4]]
        x1 = clamp((x_center - box_w / 2) * width, 0, width)
        y1 = clamp((y_center - box_h / 2) * height, 0, height)
        x2 = clamp((x_center + box_w / 2) * width, 0, width)
        y2 = clamp((y_center + box_h / 2) * height, 0, height)
        text = str(texts[idx] or "").strip()
        ui_type = str(ui_types[idx] or "").strip()
        label = f"{idx}:{ui_type}" + (f":{text[:18]}" if text else "")
        box = Box(x1, y1, x2, y2, label)
        if box.valid():
            boxes.append(box)
    return boxes


def row_boxes(target: Box, boxes: list[Box], min_height: float = 0) -> list[Box]:
    tolerance = max(20, target.height * 1.5, min_height)
    row = []
    for box in boxes:
        center_close = abs(box.cy - target.cy) <= tolerance
        overlap = not (box.y2 < target.y1 or box.y1 > target.y2)
        if center_close or overlap:
            row.append(box)
    return row


def is_search_like(box: Box, row: list[Box], task: str) -> bool:
    label = box_text(box)
    ui_label = box.label.upper()
    return "search" in label or "ICON_MAGNIFYING_GLASS" in ui_label


def search_related_boxes(row: list[Box], target: Box) -> list[Box]:
    related = []
    max_gap = max(70, target.width * 2.5)
    for box in row:
        label = box_text(box)
        ui_label = box.label.upper()
        gap = max(0, max(box.x1 - target.x2, target.x1 - box.x2))
        searchish = (
            "search" in label
            or "ICON_MAGNIFYING_GLASS" in ui_label
            or "ICON_MIC" in ui_label
            or "ICON_TAKE_PHOTO" in ui_label
            or "ICON_X" in ui_label
        )
        if searchish and gap <= max_gap and abs(box.cy - target.cy) <= max(28, target.height * 2.0):
            related.append(box)
    return related or [target]


def is_button_like(box: Box) -> bool:
    label = box_text(box)
    words = [
        "add to cart",
        "buy it",
        "buy now",
        "checkout",
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
    return any(word in label for word in words)


def is_full_width_cta(box: Box) -> bool:
    label = box_text(box)
    words = [
        "sign in to check out",
        "checkout",
        "buy it now",
        "buy now",
        "add to cart",
        "view in cart",
        "watch",
    ]
    return any(word in label for word in words)


def row_text(row: list[Box]) -> str:
    return " ".join(box_text(box) for box in sorted(row, key=lambda item: item.x1))


def row_has_full_width_cta(row: list[Box]) -> bool:
    text = row_text(row)
    phrases = [
        "sign in to check out",
        "buy it now",
        "buy now",
        "add to cart",
        "view in cart",
        "watch",
        "checkout",
    ]
    return any(isinstance(phrase, str) and phrase in text for phrase in phrases) or (
        "sign" in text and "check out" in text
    )


def is_compact_control(box: Box) -> bool:
    label = box_text(box)
    words = ["best match", "filter", "sort", "condition", "screen size", "maximum", "quantity"]
    return any(word in label for word in words)


def box_text(box: Box) -> str:
    parts = box.label.split(":", 2)
    if len(parts) == 3:
        return parts[2].lower()
    return box.label.lower()


def horizontally_related(row: list[Box], target: Box, max_gap: float) -> list[Box]:
    related = []
    for box in sorted(row, key=lambda item: item.x1):
        gap = max(0, max(box.x1 - target.x2, target.x1 - box.x2))
        if gap <= max_gap:
            related.append(box)
    return related or [target]


def is_product_task(task: str) -> bool:
    words = ["product", "item", "result", "cart", "macbook", "ebay", "amazon", "walmart", "bestbuy", "costco"]
    return any(word in task.lower() for word in words)


def processed_boxes(boxes: list[Box], width: int, height: int, task: str, merge_cards: bool) -> list[Box]:
    processed: list[Box] = []

    for box in boxes:
        row = row_boxes(box, boxes)
        if is_search_like(box, row, task):
            row_union = union(search_related_boxes(row, box), width, height, pad_x=10, pad_y=max(8, box.height * 0.35), label="search_or_suggestion_row")
            processed.append(
                Box(
                    max(0, row_union.x1 - 8),
                    row_union.y1,
                    min(width, row_union.x2 + 8),
                    row_union.y2,
                    "search_or_suggestion_row",
                )
            )
        elif is_full_width_cta(box) or row_has_full_width_cta(row):
            button_height = max(52, box.height * 2.7)
            processed.append(
                Box(
                    width * 0.04,
                    clamp(box.cy - button_height / 2, 0, height),
                    width * 0.96,
                    clamp(box.cy + button_height / 2, 0, height),
                    "full_width_cta_button",
                )
            )
        elif is_compact_control(box):
            related = horizontally_related(row, box, max_gap=max(48, box.width * 2.2))
            processed.append(
                union(
                    related,
                    width,
                    height,
                    pad_x=max(24, box.width * 0.35),
                    pad_y=max(18, box.height * 0.95),
                    label="compact_control_button",
                )
            )
        elif is_button_like(box):
            processed.append(
                expand(
                    box,
                    width,
                    height,
                    x_pad=max(24, box.width * 0.55),
                    y_pad=max(10, box.height * 0.65),
                    label="button_like",
                )
            )
        elif merge_cards and is_product_task(task) and ("TEXT" in box.label or box.height > 60):
            nearby = []
            for other in boxes:
                vertical_gap = max(0, max(other.y1 - box.y2, box.y1 - other.y2))
                horizontal_overlap = min(other.x2, box.x2) - max(other.x1, box.x1)
                same_column = horizontal_overlap > -width * 0.20
                if vertical_gap <= max(120, box.height * 3.0) and same_column:
                    nearby.append(other)
            processed.append(union(nearby or [box], width, height, pad_x=10, pad_y=10, label="possible_card_region"))
        else:
            processed.append(
                expand(
                    box,
                    width,
                    height,
                    x_pad=max(6, box.width * 0.12),
                    y_pad=max(4, box.height * 0.12),
                    label="padded_raw_bbox",
                )
            )

    return dedupe_boxes(processed)


def dedupe_boxes(boxes: list[Box]) -> list[Box]:
    seen = set()
    deduped = []
    for box in boxes:
        key = (
            round(box.x1 / 6) * 6,
            round(box.y1 / 6) * 6,
            round(box.x2 / 6) * 6,
            round(box.y2 / 6) * 6,
            box.label,
        )
        if key not in seen and box.valid():
            seen.add(key)
            deduped.append(box)
    return deduped


def draw_boxes(image_path: Path, boxes: list[Box], output_path: Path, color: tuple[int, int, int, int], title: str) -> None:
    with Image.open(image_path).convert("RGB") as image:
        draw = ImageDraw.Draw(image, "RGBA")
        for box in boxes:
            draw.rectangle([box.x1, box.y1, box.x2, box.y2], outline=color, width=3)
        draw_title(draw, title)
        image.save(output_path)


def draw_title(draw: ImageDraw.ImageDraw, title: str) -> None:
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((8, 8), title, font=font)
    draw.rectangle([bbox[0] - 4, bbox[1] - 3, bbox[2] + 4, bbox[3] + 3], fill=(255, 255, 255, 230))
    draw.text((8, 8), title, fill=(0, 0, 0, 255), font=font)


def image_path_for(record: dict, root: Path) -> Path:
    value = record.get("image_encoded") or record.get("image") or record.get("screenshot")
    if isinstance(value, dict):
        value = value.get("path")
    if not isinstance(value, str):
        raise ValueError("record has no image path")
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def write_html(records: list[dict], output_path: Path) -> None:
    cards = []
    for record in records:
        raw_rel = Path(record["raw_output"]).relative_to(output_path.parent).as_posix()
        processed_rel = Path(record["processed_output"]).relative_to(output_path.parent).as_posix()
        cards.append(
            f"""
            <article>
              <h2>#{record['index']} raw={record['raw_count']} processed={record['processed_count']}</h2>
              <p><b>goal:</b> {html.escape(record['goal'])}</p>
              <div class="pair">
                <figure><img src="{html.escape(raw_rel)}"><figcaption>raw image_ui_annotations_positions</figcaption></figure>
                <figure><img src="{html.escape(processed_rel)}"><figcaption>processed / estimated effective regions</figcaption></figure>
              </div>
            </article>
            """
        )

    output_path.write_text(
        f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Raw vs Processed UI BBox Regions</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f6f7f9; }}
    header {{ padding: 16px 20px; background: white; border-bottom: 1px solid #ddd; position: sticky; top: 0; z-index: 2; }}
    main {{ padding: 16px; display: grid; gap: 18px; }}
    article {{ background: white; border: 1px solid #d8dde6; border-radius: 8px; padding: 12px; }}
    h1 {{ margin: 0 0 8px; font-size: 20px; }}
    h2 {{ margin: 0 0 8px; font-size: 16px; }}
    p {{ font-size: 13px; }}
    .pair {{ display: grid; grid-template-columns: repeat(2, minmax(280px, 1fr)); gap: 12px; align-items: start; }}
    figure {{ margin: 0; }}
    img {{ width: 100%; height: auto; border: 1px solid #ddd; background: #fff; }}
    figcaption {{ font-size: 13px; margin-top: 6px; color: #444; }}
  </style>
</head>
<body>
  <header>
    <h1>Raw vs Processed UI BBox Regions</h1>
    <div>Left: original boxes from image_ui_annotations_positions. Right: boxes after low-cost effective-region rules.</div>
  </header>
  <main>{''.join(cards)}</main>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/aitw_single/unseen_subject_train_1000_with_images.jsonl")
    parser.add_argument("--output-dir", default="reports/ui_annotation_regions")
    parser.add_argument("--image-root", default=".")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--seed", type=int, default=9)
    parser.add_argument("--merge-cards", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    raw_dir = output_dir / "raw"
    processed_dir = output_dir / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    records = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    random.Random(args.seed).shuffle(records)

    output_records = []
    root = Path(args.image_root)
    for record in records:
        image_path = image_path_for(record, root)
        if not image_path.exists():
            continue
        with Image.open(image_path) as image:
            width, height = image.size

        boxes = raw_boxes(record, width, height)
        if not boxes:
            continue

        idx = len(output_records)
        new_boxes = processed_boxes(boxes, width, height, record.get("goal_info", ""), args.merge_cards)
        raw_output = raw_dir / f"{idx:04d}_raw_boxes.png"
        processed_output = processed_dir / f"{idx:04d}_processed_boxes.png"
        draw_boxes(image_path, boxes, raw_output, (0, 122, 255, 255), "raw image_ui_annotations_positions")
        draw_boxes(image_path, new_boxes, processed_output, (255, 149, 0, 255), "processed effective regions")

        output_records.append(
            {
                "index": idx,
                "image": str(image_path),
                "goal": record.get("goal_info", ""),
                "raw_count": len(boxes),
                "processed_count": len(new_boxes),
                "raw_output": str(raw_output),
                "processed_output": str(processed_output),
            }
        )
        if len(output_records) >= args.limit:
            break

    html_path = output_dir / "raw_vs_processed_regions.html"
    metadata_path = output_dir / "raw_vs_processed_regions.json"
    write_html(output_records, html_path)
    metadata_path.write_text(json.dumps(output_records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "input": str(input_path),
                "num_samples": len(output_records),
                "html": str(html_path),
                "metadata": str(metadata_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
