import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from mobile_gui_agent_data.schemas import ActionType, PreferencePair
from mobile_gui_agent_data.utils.effective_regions import (
    EffectiveRegion,
    action_effective_region,
    action_point_pixels,
    point_in_effective_region,
)


FUNCTIONAL_REGION_KINDS = {
    "search_or_suggestion_row",
    "full_width_cta_button",
    "compact_control_button",
    "product_card_region",
}

HIGH_CONFIDENCE_FILTER_KINDS = {
    "full_width_cta_button",
    "compact_control_button",
}


def region_overlap(a: EffectiveRegion | None, b: EffectiveRegion | None) -> float:
    if a is None or b is None:
        return 0.0
    x1 = max(a.box.x1, b.box.x1)
    y1 = max(a.box.y1, b.box.y1)
    x2 = min(a.box.x2, b.box.x2)
    y2 = min(a.box.y2, b.box.y2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    overlap = (x2 - x1) * (y2 - y1)
    return overlap / max(1.0, min(a.box.area, b.box.area))


def classify_pair(pair: PreferencePair) -> dict[str, Any]:
    step = pair.step
    chosen = pair.chosen
    rejected = pair.rejected
    negative_subtype = str(rejected.metadata.get("negative_subtype", "unknown"))

    base = {
        "pair_id": pair.pair_id,
        "episode_id": step.episode_id,
        "step_id": step.step_id,
        "task": step.task,
        "negative_type": pair.negative_type,
        "negative_subtype": negative_subtype,
        "chosen_action_type": chosen.type.value,
        "rejected_action_type": rejected.type.value,
        "image": step.screenshot_before,
    }

    if rejected.type in {ActionType.SWIPE, ActionType.SCROLL} or chosen.type in {ActionType.SWIPE, ActionType.SCROLL}:
        return {
            **base,
            "decision": "ambiguous",
            "reason": "swipe_or_scroll_uncertain",
            "major_category": "ambiguous_or_uncertain",
        }

    if rejected.type != ActionType.CLICK:
        if pair.negative_type == "wrong_action_type":
            return {
                **base,
                "decision": "keep",
                "reason": "wrong_action_type_non_click",
                "major_category": "wrong_action_type",
            }
        return {
            **base,
            "decision": "ambiguous",
            "reason": "non_click_candidate_unchecked",
            "major_category": "ambiguous_or_uncertain",
        }

    if chosen.type != ActionType.CLICK:
        if pair.negative_type == "wrong_action_type":
            return {
                **base,
                "decision": "keep",
                "reason": "wrong_action_type_click_instead_of_non_click",
                "major_category": "wrong_action_type",
            }
        return {
            **base,
            "decision": "ambiguous",
            "reason": "non_click_gt_unchecked",
            "major_category": "ambiguous_or_uncertain",
        }

    target_region = action_effective_region(step, chosen)
    candidate_region = action_effective_region(step, rejected)
    target_region_kind = target_region.kind if target_region else "none"
    candidate_region_kind = candidate_region.kind if candidate_region else "none"
    target_region_box = target_region.box.to_list() if target_region else None
    candidate_region_box = candidate_region.box.to_list() if candidate_region else None

    enriched = {
        **base,
        "target_region_kind": target_region_kind,
        "candidate_region_kind": candidate_region_kind,
        "target_region_box": target_region_box,
        "candidate_region_box": candidate_region_box,
    }

    if point_in_effective_region(rejected, step, target_region):
        if target_region_kind not in HIGH_CONFIDENCE_FILTER_KINDS:
            return {
                **enriched,
                "decision": "ambiguous",
                "reason": "candidate_inside_low_confidence_target_region",
                "major_category": "ambiguous_or_uncertain",
            }
        return {
            **enriched,
            "decision": "filter",
            "reason": "candidate_inside_high_confidence_target_region",
            "major_category": "negative_construction_error",
        }

    overlap = region_overlap(target_region, candidate_region)
    if (
        target_region_kind in HIGH_CONFIDENCE_FILTER_KINDS
        and candidate_region_kind == target_region_kind
        and overlap >= 0.5
    ):
        return {
            **enriched,
            "decision": "filter",
            "reason": "candidate_same_high_confidence_functional_region",
            "major_category": "negative_construction_error",
            "region_overlap": overlap,
        }
    if (
        target_region_kind in FUNCTIONAL_REGION_KINDS
        and candidate_region_kind == target_region_kind
        and overlap >= 0.5
    ):
        return {
            **enriched,
            "decision": "ambiguous",
            "reason": "candidate_same_low_confidence_functional_region",
            "major_category": "ambiguous_or_uncertain",
            "region_overlap": overlap,
        }

    if candidate_region is None:
        return {
            **enriched,
            "decision": "keep",
            "reason": "candidate_no_ui_region",
            "major_category": "clean_negative",
        }

    if candidate_region_kind in FUNCTIONAL_REGION_KINDS or pair.negative_type in {
        "same_screen_element",
        "shifted_coordinate",
    }:
        return {
            **enriched,
            "decision": "keep",
            "reason": "candidate_other_ui_or_functional_region",
            "major_category": "semantic_hard_negative",
        }

    return {
        **enriched,
        "decision": "keep",
        "reason": "candidate_other_ui_region",
        "major_category": "clean_negative",
    }


def read_pairs(path: Path) -> list[PreferencePair]:
    pairs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            pairs.append(PreferencePair.model_validate_json(line))
    return pairs


def summarize(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    counters = {
        "decision": Counter(),
        "reason": Counter(),
        "major_category": Counter(),
        "negative_type": Counter(),
        "negative_subtype": Counter(),
        "by_negative_type_decision": defaultdict(Counter),
        "by_negative_subtype_decision": defaultdict(Counter),
        "by_reason_negative_type": defaultdict(Counter),
    }
    for item in decisions:
        counters["decision"][item["decision"]] += 1
        counters["reason"][item["reason"]] += 1
        counters["major_category"][item["major_category"]] += 1
        counters["negative_type"][item["negative_type"]] += 1
        counters["negative_subtype"][item["negative_subtype"]] += 1
        counters["by_negative_type_decision"][item["negative_type"]][item["decision"]] += 1
        counters["by_negative_subtype_decision"][item["negative_subtype"]][item["decision"]] += 1
        counters["by_reason_negative_type"][item["reason"]][item["negative_type"]] += 1

    return {
        "num_pairs": len(decisions),
        "decision": dict(counters["decision"]),
        "reason": dict(counters["reason"]),
        "major_category": dict(counters["major_category"]),
        "negative_type": dict(counters["negative_type"]),
        "negative_subtype": dict(counters["negative_subtype"]),
        "by_negative_type_decision": {key: dict(value) for key, value in counters["by_negative_type_decision"].items()},
        "by_negative_subtype_decision": {key: dict(value) for key, value in counters["by_negative_subtype_decision"].items()},
        "by_reason_negative_type": {key: dict(value) for key, value in counters["by_reason_negative_type"].items()},
    }


def resolve_image_path(path: str | None, image_root: Path) -> Path | None:
    if not path:
        return None
    image_path = Path(path)
    if image_path.is_absolute():
        return image_path
    return image_root / image_path


def draw_box(draw: ImageDraw.ImageDraw, box: list[float | str] | None, color: tuple[int, int, int, int]) -> None:
    if not box:
        return
    x1, y1, x2, y2, _label = box
    draw.rectangle([float(x1), float(y1), float(x2), float(y2)], outline=color, width=4)


def draw_point(draw: ImageDraw.ImageDraw, point: tuple[float, float] | None, color: tuple[int, int, int, int], label: str) -> None:
    if point is None:
        return
    x, y = point
    r = 8
    draw.ellipse([x - r, y - r, x + r, y + r], fill=color, outline=(255, 255, 255, 255), width=2)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    draw.text((x + 10, y - 10), label, fill=color, font=font)


def render_case(
    pair: PreferencePair,
    decision: dict[str, Any],
    image_root: Path,
    output_path: Path,
) -> bool:
    image_path = resolve_image_path(pair.step.screenshot_before, image_root)
    if image_path is None or not image_path.exists() or pair.step.screen_size is None:
        return False

    with Image.open(image_path).convert("RGB") as image:
        draw = ImageDraw.Draw(image, "RGBA")
        draw_box(draw, decision.get("target_region_box"), (255, 149, 0, 255))
        draw_box(draw, decision.get("candidate_region_box"), (175, 82, 222, 255))
        draw_point(draw, action_point_pixels(pair.chosen, pair.step.screen_size), (0, 122, 255, 255), "GT")
        draw_point(draw, action_point_pixels(pair.rejected, pair.step.screen_size), (255, 59, 48, 255), "NEG")
        image.save(output_path)
    return True


def write_html(samples: list[dict[str, Any]], output_path: Path) -> None:
    cards = []
    for sample in samples:
        rel = Path(sample["rendered_image"]).relative_to(output_path.parent).as_posix()
        cards.append(
            f"""
            <article class="{html.escape(sample['decision'])}">
              <h2>#{sample['index']} {html.escape(sample['decision'])} / {html.escape(sample['major_category'])}</h2>
              <p><b>reason:</b> {html.escape(sample['reason'])}</p>
              <p><b>negative:</b> {html.escape(sample['negative_type'])} / {html.escape(sample['negative_subtype'])}</p>
              <p><b>regions:</b> target={html.escape(sample.get('target_region_kind', 'none'))}, candidate={html.escape(sample.get('candidate_region_kind', 'none'))}</p>
              <p><b>task:</b> {html.escape(sample['task'])}</p>
              <img src="{html.escape(rel)}" />
            </article>
            """
        )
    output_path.write_text(
        f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>V3 Negative Filter Dry Run</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f6f7f9; }}
    header {{ padding: 16px 20px; background: white; border-bottom: 1px solid #ddd; position: sticky; top: 0; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 16px; padding: 16px; }}
    article {{ background: white; border: 1px solid #d8dde6; border-radius: 8px; padding: 12px; }}
    article.filter {{ border-color: #ff9500; }}
    article.ambiguous {{ border-color: #8e8e93; }}
    article.keep {{ border-color: #34c759; }}
    h1 {{ margin: 0 0 8px; font-size: 20px; }}
    h2 {{ margin: 0 0 8px; font-size: 16px; }}
    p {{ font-size: 13px; line-height: 1.35; }}
    img {{ width: 100%; height: auto; border: 1px solid #ddd; }}
    .legend span {{ display: inline-block; margin-right: 16px; }}
  </style>
</head>
<body>
  <header>
    <h1>V3 Negative Filter Dry Run</h1>
    <div class="legend">
      <span style="color:#007aff">blue dot = GT action</span>
      <span style="color:#ff3b30">red dot = rejected action</span>
      <span style="color:#ff9500">orange box = GT effective region</span>
      <span style="color:#af52de">purple box = rejected effective region</span>
    </div>
  </header>
  <main>{''.join(cards)}</main>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_recovered_html(samples: list[dict[str, Any]], output_path: Path) -> None:
    cards = []
    for sample in samples:
        rel = Path(sample["rendered_image"]).relative_to(output_path.parent).as_posix()
        cards.append(
            f"""
            <article>
              <h2>#{sample['index']} {html.escape(sample['reason'])}</h2>
              <p><b>old label:</b> No / rejected action</p>
              <p><b>new rule:</b> filter from strong negatives</p>
              <p><b>negative:</b> {html.escape(sample['negative_type'])} / {html.escape(sample['negative_subtype'])}</p>
              <p><b>GT region:</b> {html.escape(sample.get('target_region_kind', 'none'))}</p>
              <p><b>candidate region:</b> {html.escape(sample.get('candidate_region_kind', 'none'))}</p>
              <p><b>task:</b> {html.escape(sample['task'])}</p>
              <img src="{html.escape(rel)}" />
            </article>
            """
        )
    output_path.write_text(
        f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Recovered Positive / Label Noise Candidates</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f6f7f9; }}
    header {{ padding: 16px 20px; background: white; border-bottom: 1px solid #ddd; position: sticky; top: 0; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 16px; padding: 16px; }}
    article {{ background: white; border: 1px solid #ff9500; border-radius: 8px; padding: 12px; }}
    h1 {{ margin: 0 0 8px; font-size: 20px; }}
    h2 {{ margin: 0 0 8px; font-size: 16px; }}
    p {{ font-size: 13px; line-height: 1.35; }}
    img {{ width: 100%; height: auto; border: 1px solid #ddd; }}
    .legend span {{ display: inline-block; margin-right: 16px; }}
  </style>
</head>
<body>
  <header>
    <h1>Recovered Positive / Label Noise Candidates</h1>
    <div>These samples were labeled as No before, but the rejected action now falls inside the GT effective region or the same functional region.</div>
    <div class="legend">
      <span style="color:#007aff">blue dot = GT action</span>
      <span style="color:#ff3b30">red dot = old negative action</span>
      <span style="color:#ff9500">orange box = GT effective region</span>
      <span style="color:#af52de">purple box = rejected effective region</span>
    </div>
  </header>
  <main>{''.join(cards)}</main>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def select_samples(decisions: list[dict[str, Any]], per_decision: int) -> list[dict[str, Any]]:
    selected = []
    counts = Counter()
    for decision in decisions:
        key = decision["decision"]
        if counts[key] < per_decision:
            selected.append(decision)
            counts[key] += 1
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", default="reports/v3_negative_filter_dry_run")
    parser.add_argument("--image-root", default=".")
    parser.add_argument("--html-samples-per-decision", type=int, default=24)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    pairs = read_pairs(input_path)
    decisions = [classify_pair(pair) for pair in pairs]
    summary = summarize(decisions)

    decisions_path = output_dir / "v3_negative_filter_decisions.jsonl"
    summary_path = output_dir / "v3_negative_filter_summary.json"
    html_path = output_dir / "v3_negative_filter_samples.html"
    recovered_html_path = output_dir / "v3_recovered_positive_candidates.html"
    recovered_jsonl_path = output_dir / "v3_recovered_positive_candidates.jsonl"

    write_jsonl(decisions, decisions_path)
    summary_path.write_text(json.dumps({"input": str(input_path), **summary}, ensure_ascii=False, indent=2), encoding="utf-8")

    pair_map = {pair.pair_id: pair for pair in pairs}
    html_samples = []
    for sample in select_samples(decisions, args.html_samples_per_decision):
        pair = pair_map[sample["pair_id"]]
        rendered = image_dir / f"{len(html_samples):04d}_{sample['decision']}.png"
        if render_case(pair, sample, Path(args.image_root), rendered):
            html_samples.append({**sample, "index": len(html_samples), "rendered_image": str(rendered)})
    write_html(html_samples, html_path)

    recovered = [decision for decision in decisions if decision["decision"] == "filter"]
    write_jsonl(recovered, recovered_jsonl_path)
    recovered_samples = []
    for sample in recovered:
        pair = pair_map[sample["pair_id"]]
        rendered = image_dir / f"recovered_{len(recovered_samples):04d}.png"
        if render_case(pair, sample, Path(args.image_root), rendered):
            recovered_samples.append({**sample, "index": len(recovered_samples), "rendered_image": str(rendered)})
    write_recovered_html(recovered_samples, recovered_html_path)

    print(
        json.dumps(
            {
                "input": str(input_path),
                "summary": str(summary_path),
                "decisions": str(decisions_path),
                "html": str(html_path),
                "recovered_html": str(recovered_html_path),
                "recovered_jsonl": str(recovered_jsonl_path),
                "num_pairs": len(decisions),
                "decision": summary["decision"],
                "major_category": summary["major_category"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
