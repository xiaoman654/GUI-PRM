import argparse
import html
import json
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any

from mobile_gui_agent_data.schemas import GUIAction, PreferencePair, ScreenSize, StepSample, UIElement
from mobile_gui_agent_data.scorer.dataset import action_to_text
from mobile_gui_agent_data.utils.coordinates import bbox_to_pixel, point_to_pixel


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_jsonl(path: str | Path, records: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def candidate_action_type(record: dict[str, Any]) -> str:
    action = record.get("candidate_action") or {}
    return str(action.get("type", "unknown"))


def candidate_negative_subtype(record: dict[str, Any]) -> str:
    action = record.get("candidate_action") or {}
    metadata = action.get("metadata") or {}
    if not isinstance(metadata, dict):
        return "unknown"
    return str(metadata.get("negative_subtype") or metadata.get("negative_source") or "unknown")


def action_primary_point(action: GUIAction | dict[str, Any]) -> tuple[float, float] | None:
    if isinstance(action, GUIAction):
        return action.primary_point()
    point = action.get("point") or action.get("start_point")
    if not isinstance(point, list | tuple) or len(point) != 2:
        return None
    return float(point[0]), float(point[1])


def action_coordinate_space(action: GUIAction | dict[str, Any]) -> str:
    if isinstance(action, GUIAction):
        return action.coordinate_space
    return str(action.get("coordinate_space") or "pixel")


def point_distance_px(
    candidate_action: dict[str, Any],
    gt_action: GUIAction,
    screen_size: ScreenSize | None,
) -> float | None:
    if screen_size is None:
        return None
    candidate_point = action_primary_point(candidate_action)
    gt_point = action_primary_point(gt_action)
    if candidate_point is None or gt_point is None:
        return None
    candidate_px = point_to_pixel(candidate_point, screen_size, action_coordinate_space(candidate_action))
    gt_px = point_to_pixel(gt_point, screen_size, gt_action.coordinate_space)
    return math.dist(candidate_px, gt_px)


def distance_bucket(distance: float | None) -> str:
    if distance is None:
        return "unknown"
    if distance <= 20:
        return "0-20px"
    if distance <= 50:
        return "20-50px"
    if distance <= 100:
        return "50-100px"
    return "100px+"


def point_in_element(
    point: tuple[float, float],
    point_space: str,
    element: UIElement,
    screen_size: ScreenSize,
) -> bool:
    x, y = point_to_pixel(point, screen_size, point_space)
    bbox = bbox_to_pixel(element.bbox, screen_size)
    return bbox.x1 <= x <= bbox.x2 and bbox.y1 <= y <= bbox.y2


def element_for_action(
    action: GUIAction | dict[str, Any],
    step: StepSample | None,
) -> UIElement | None:
    if step is None or step.screen_size is None:
        return None
    point = action_primary_point(action)
    if point is None:
        return None
    point_space = action_coordinate_space(action)
    for element in step.ui_elements:
        if point_in_element(point, point_space, element, step.screen_size):
            return element
    return None


def element_summary(element: UIElement | None) -> dict[str, Any] | None:
    if element is None:
        return None
    return {
        "index": element.index,
        "text": element.text,
        "ui_type": element.ui_type,
        "bbox": element.bbox.model_dump(mode="json"),
    }


def load_pair_index(path: str | Path | None) -> dict[str, PreferencePair]:
    if path is None:
        return {}
    pairs = {}
    for raw in read_jsonl(path):
        pair = PreferencePair(**raw)
        pairs[pair.pair_id] = pair
    return pairs


def is_error(record: dict[str, Any]) -> bool:
    if "correct" in record:
        return not bool(record["correct"])
    return str(record.get("label")) != str(record.get("prediction_label"))


def image_src(image: str, image_root: str | Path | None, html_dir: Path) -> str:
    image_path = Path(image)
    if not image_path.is_absolute() and image_root is not None:
        image_path = Path(image_root) / image_path
    if image_path.is_absolute() and image_root is not None:
        root_path = Path(image_root).resolve()
        try:
            image_path.resolve().relative_to(root_path)
            relative_path = os.path.relpath(image_path, html_dir)
            return html.escape(Path(relative_path).as_posix())
        except ValueError:
            pass
    if image_path.is_absolute():
        return image_path.as_uri()
    return html.escape(image_path.as_posix())


def normalized_point_style(point: Any) -> str | None:
    if not isinstance(point, list | tuple) or len(point) != 2:
        return None
    try:
        x = max(0.0, min(1.0, float(point[0])))
        y = max(0.0, min(1.0, float(point[1])))
    except (TypeError, ValueError):
        return None
    return f"left: {x * 100:.3f}%; top: {y * 100:.3f}%;"


def markers_for_action(action: dict[str, Any], marker_kind: str, label_prefix: str) -> str:
    action_type = str(action.get("type", ""))
    markers = []
    if action_type == "click":
        style = normalized_point_style(action.get("point"))
        if style:
            markers.append(
                f'<span class="marker {marker_kind}" style="{style}" title="{label_prefix} click"></span>'
            )
    elif action_type in {"swipe", "scroll"}:
        start_style = normalized_point_style(action.get("start_point"))
        end_style = normalized_point_style(action.get("end_point"))
        if start_style:
            markers.append(
                f'<span class="marker {marker_kind}-start" style="{start_style}" title="{label_prefix} swipe start">S</span>'
            )
        if end_style:
            markers.append(
                f'<span class="marker {marker_kind}-end" style="{end_style}" title="{label_prefix} swipe end">E</span>'
            )
    return "".join(markers)


def action_markers(record: dict[str, Any]) -> str:
    markers = markers_for_action(record.get("candidate_action") or {}, "candidate", "candidate")
    gt_action = record.get("gt_action")
    if isinstance(gt_action, dict):
        markers += markers_for_action(gt_action, "gt", "ground truth")
    return markers


def screen_aspect_ratio(record: dict[str, Any], pair: PreferencePair | None = None) -> str:
    screen_size = record.get("screen_size") or {}
    if pair is not None and pair.step.screen_size is not None:
        screen_size = pair.step.screen_size.model_dump(mode="json")
    try:
        width = int(screen_size.get("width") or 720)
        height = int(screen_size.get("height") or 1520)
    except (TypeError, ValueError):
        width, height = 720, 1520
    return f"{max(width, 1)} / {max(height, 1)}"


def render_html(records: list[dict[str, Any]], output_path: str | Path, limit: int, image_root: str | Path | None) -> None:
    html_path = Path(output_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    shown_records = records[:limit]

    cards = []
    for idx, record in enumerate(shown_records, start=1):
        label = html.escape(str(record.get("label", "")))
        pred = html.escape(str(record.get("prediction_label", "")))
        negative_type = html.escape(str(record.get("negative_type", "")))
        action_type = html.escape(candidate_action_type(record))
        instruction = html.escape(str(record.get("instruction", "")))
        action = html.escape(str(record.get("candidate_action_text", "")))
        gt_action = html.escape(str(record.get("gt_action_text", "")))
        raw_pred = html.escape(str(record.get("prediction_raw", "")))
        distance = html.escape(str(record.get("distance_bucket", "")))
        candidate_element = html.escape(str(record.get("candidate_element_text", "")))
        gt_element = html.escape(str(record.get("gt_element_text", "")))
        src = image_src(str(record.get("image", "")), image_root, html_path.parent)
        markers = action_markers(record)
        aspect_ratio = screen_aspect_ratio(record)
        cards.append(
            f"""
            <section class="card">
              <div class="meta">
                <strong>#{idx}</strong>
                <span>{label} -> {pred}</span>
                <span>{negative_type}</span>
                <span>{action_type}</span>
                <span>{distance}</span>
              </div>
              <div class="screen" style="aspect-ratio: {aspect_ratio};">
                <img src="{src}" alt="screen {idx}" />
                {markers}
              </div>
              <div class="text"><strong>Instruction</strong><br>{instruction}</div>
              <div class="text"><strong>Candidate</strong><br><code>{action}</code></div>
              <div class="text"><strong>Ground truth</strong><br><code>{gt_action}</code></div>
              <div class="text"><strong>Elements</strong><br>candidate: {candidate_element}<br>ground truth: {gt_element}</div>
              <div class="text"><strong>Raw prediction</strong><br><code>{raw_pred}</code></div>
            </section>
            """
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Scorer Error Inspection</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f6f7f9;
      color: #17191f;
    }}
    header {{
      position: sticky;
      top: 0;
      padding: 16px 24px;
      background: #ffffff;
      border-bottom: 1px solid #d9dde5;
      z-index: 1;
    }}
    main {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 16px;
      padding: 16px;
    }}
    .card {{
      background: #ffffff;
      border: 1px solid #d9dde5;
      border-radius: 8px;
      overflow: hidden;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 10px;
      font-size: 13px;
      border-bottom: 1px solid #eceff4;
    }}
    .meta span {{
      padding: 2px 6px;
      background: #eef1f6;
      border-radius: 4px;
    }}
    .screen {{
      position: relative;
      width: 100%;
      max-height: 520px;
      background: #111318;
      overflow: hidden;
    }}
    img {{
      position: absolute;
      inset: 0;
      display: block;
      width: 100%;
      height: 100%;
      object-fit: fill;
    }}
    .marker {{
      position: absolute;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      transform: translate(-50%, -50%);
      box-sizing: border-box;
      z-index: 2;
      box-shadow: 0 0 0 2px #ffffff, 0 2px 8px rgba(0, 0, 0, 0.45);
      font-size: 10px;
      line-height: 18px;
      text-align: center;
      font-weight: 700;
      color: #ffffff;
    }}
    .marker.candidate {{
      background: #e11900;
      border: 2px solid #7a0b00;
    }}
    .marker.candidate-start {{
      background: #098b45;
      border: 2px solid #004d24;
    }}
    .marker.candidate-end {{
      background: #e11900;
      border: 2px solid #7a0b00;
    }}
    .marker.gt {{
      background: #1769ff;
      border: 2px solid #00358f;
    }}
    .marker.gt-start {{
      background: #00a3a3;
      border: 2px solid #005d5d;
    }}
    .marker.gt-end {{
      background: #1769ff;
      border: 2px solid #00358f;
    }}
    .text {{
      padding: 10px;
      font-size: 13px;
      line-height: 1.45;
      border-top: 1px solid #eceff4;
      overflow-wrap: anywhere;
    }}
    code {{
      font-family: Consolas, Menlo, monospace;
    }}
  </style>
</head>
<body>
  <header>
    <strong>Scorer Error Inspection</strong>
    <span>{len(records)} errors, showing {len(shown_records)}</span>
  </header>
  <main>
    {''.join(cards)}
  </main>
</body>
</html>
"""
    html_path.write_text(document, encoding="utf-8")


def enrich_error(record: dict[str, Any], pair: PreferencePair | None) -> dict[str, Any]:
    enriched = dict(record)
    if pair is None:
        enriched.setdefault("distance_bucket", "unknown")
        return enriched

    gt_action = pair.chosen
    candidate_action = record.get("candidate_action") or {}
    candidate_element = element_for_action(candidate_action, pair.step)
    gt_element = element_for_action(gt_action, pair.step)
    distance = point_distance_px(candidate_action, gt_action, pair.step.screen_size)
    same_element = (
        candidate_element is not None
        and gt_element is not None
        and candidate_element.index == gt_element.index
    )
    enriched.update(
        {
            "gt_action": gt_action.model_dump(mode="json"),
            "gt_action_text": action_to_text(gt_action.model_dump(mode="json")),
            "candidate_element": element_summary(candidate_element),
            "gt_element": element_summary(gt_element),
            "candidate_element_text": candidate_element.text if candidate_element else "",
            "gt_element_text": gt_element.text if gt_element else "",
            "candidate_in_ui_element": candidate_element is not None,
            "same_element_as_gt": same_element,
            "distance_px": distance,
            "distance_bucket": distance_bucket(distance),
        }
    )
    return enriched


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Prediction JSONL produced by evaluate_qwen_vl_scorer.py")
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--errors-output", default=None)
    parser.add_argument("--html-output", default=None)
    parser.add_argument("--image-root", default=None)
    parser.add_argument("--pairs", default=None, help="Preference pair JSONL used to recover ground-truth action and UI elements")
    parser.add_argument("--focus", default=None, help="Optional confusion filter, such as No->Yes")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    pair_index = load_pair_index(args.pairs)
    records = read_jsonl(args.input)
    errors = [record for record in records if is_error(record)]
    if args.focus:
        errors = [
            record
            for record in errors
            if f"{record.get('label')}->{record.get('prediction_label')}" == args.focus
        ]
    errors = [enrich_error(record, pair_index.get(str(record.get("pair_id")))) for record in errors]

    summary = {
        "input": args.input,
        "num_records": len(records),
        "num_errors": len(errors),
        "focus": args.focus,
        "error_confusion": dict(
            Counter(f"{record.get('label')}->{record.get('prediction_label')}" for record in errors).most_common()
        ),
        "negative_type": dict(
            Counter(record.get("negative_type") for record in errors if str(record.get("label")) == "No").most_common()
        ),
        "candidate_action_type": dict(Counter(candidate_action_type(record) for record in errors).most_common()),
        "negative_subtype": dict(
            Counter(candidate_negative_subtype(record) for record in errors if str(record.get("label")) == "No").most_common()
        ),
        "distance_bucket": dict(Counter(record.get("distance_bucket", "unknown") for record in errors).most_common()),
        "candidate_in_ui_element": dict(Counter(str(record.get("candidate_in_ui_element", "unknown")) for record in errors).most_common()),
        "same_element_as_gt": dict(Counter(str(record.get("same_element_as_gt", "unknown")) for record in errors).most_common()),
        "instructions": dict(Counter(str(record.get("instruction", "")) for record in errors).most_common(20)),
    }

    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.errors_output:
        write_jsonl(args.errors_output, errors)
    if args.html_output:
        render_html(errors, args.html_output, args.limit, args.image_root)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
