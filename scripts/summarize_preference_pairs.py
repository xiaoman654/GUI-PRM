import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from mobile_gui_agent_data.schemas import GUIAction, PreferencePair, ScreenSize, StepSample, UIElement
from mobile_gui_agent_data.utils.coordinates import bbox_to_pixel, point_to_pixel
from mobile_gui_agent_data.utils.io import read_jsonl


def primary_point(action: GUIAction) -> tuple[float, float] | None:
    return action.primary_point()


def point_in_element(
    point: tuple[float, float],
    point_space: str,
    element: UIElement,
    screen_size: ScreenSize,
) -> bool:
    x, y = point_to_pixel(point, screen_size, point_space)
    bbox = bbox_to_pixel(element.bbox, screen_size)
    return bbox.x1 <= x <= bbox.x2 and bbox.y1 <= y <= bbox.y2


def element_for_action(action: GUIAction, step: StepSample) -> UIElement | None:
    point = primary_point(action)
    if point is None or step.screen_size is None:
        return None
    for element in step.ui_elements:
        if point_in_element(point, action.coordinate_space, element, step.screen_size):
            return element
    return None


def distance_px(action_a: GUIAction, action_b: GUIAction, screen_size: ScreenSize | None) -> float | None:
    point_a = primary_point(action_a)
    point_b = primary_point(action_b)
    if point_a is None or point_b is None or screen_size is None:
        return None
    pixel_a = point_to_pixel(point_a, screen_size, action_a.coordinate_space)
    pixel_b = point_to_pixel(point_b, screen_size, action_b.coordinate_space)
    return math.dist(pixel_a, pixel_b)


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


def counter_to_dict(counter: Counter) -> dict[str, int]:
    return {str(key): value for key, value in counter.most_common()}


def nested_counter_to_dict(counter: dict[str, Counter]) -> dict[str, dict[str, int]]:
    return {key: counter_to_dict(value) for key, value in sorted(counter.items())}


def summarize_pairs(path: str | Path) -> dict[str, Any]:
    negative_types = Counter()
    negative_subtypes = Counter()
    rejected_action_types = Counter()
    chosen_action_types = Counter()
    transition_types = Counter()
    distance_buckets = Counter()
    rejected_in_ui = Counter()
    same_element_as_gt = Counter()
    subtype_by_negative_type: dict[str, Counter] = defaultdict(Counter)
    rejected_action_by_negative_type: dict[str, Counter] = defaultdict(Counter)
    rejected_ui_type = Counter()

    num_pairs = 0
    for raw in read_jsonl(path):
        pair = PreferencePair(**raw)
        num_pairs += 1
        negative_type = pair.negative_type
        negative_subtype = str(pair.rejected.metadata.get("negative_subtype", "unknown"))
        rejected_type = pair.rejected.type.value
        chosen_type = pair.chosen.type.value

        negative_types[negative_type] += 1
        negative_subtypes[negative_subtype] += 1
        rejected_action_types[rejected_type] += 1
        chosen_action_types[chosen_type] += 1
        transition_types[f"{chosen_type}->{rejected_type}"] += 1
        subtype_by_negative_type[negative_type][negative_subtype] += 1
        rejected_action_by_negative_type[negative_type][rejected_type] += 1

        gt_element = element_for_action(pair.chosen, pair.step)
        rejected_element = element_for_action(pair.rejected, pair.step)
        rejected_in_ui[str(rejected_element is not None)] += 1
        same_element_as_gt[str(
            gt_element is not None
            and rejected_element is not None
            and gt_element.index == rejected_element.index
        )] += 1
        if rejected_element is not None:
            rejected_ui_type[rejected_element.ui_type or "unknown"] += 1

        distance_buckets[distance_bucket(distance_px(pair.rejected, pair.chosen, pair.step.screen_size))] += 1

    return {
        "input": str(path),
        "num_pairs": num_pairs,
        "negative_types": counter_to_dict(negative_types),
        "negative_subtypes": counter_to_dict(negative_subtypes),
        "chosen_action_types": counter_to_dict(chosen_action_types),
        "rejected_action_types": counter_to_dict(rejected_action_types),
        "transition_types": counter_to_dict(transition_types),
        "subtype_by_negative_type": nested_counter_to_dict(subtype_by_negative_type),
        "rejected_action_by_negative_type": nested_counter_to_dict(rejected_action_by_negative_type),
        "distance_bucket": counter_to_dict(distance_buckets),
        "rejected_in_ui_element": counter_to_dict(rejected_in_ui),
        "same_element_as_gt": counter_to_dict(same_element_as_gt),
        "rejected_ui_type": counter_to_dict(rejected_ui_type),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    summary = summarize_pairs(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
