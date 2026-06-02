from collections.abc import Sequence

from mobile_gui_agent_data.schemas import BoundingBox, ScreenSize
from mobile_gui_agent_data.utils.coordinates import bbox_to_pixel, point_to_pixel


def top_k_accuracy(ranked_ids: Sequence[Sequence[str]], gold_ids: Sequence[str], k: int = 1) -> float:
    hits = 0
    for ranked, gold in zip(ranked_ids, gold_ids, strict=True):
        hits += int(gold in ranked[:k])
    return hits / max(len(gold_ids), 1)


def mean_reciprocal_rank(ranked_ids: Sequence[Sequence[str]], gold_ids: Sequence[str]) -> float:
    total = 0.0
    for ranked, gold in zip(ranked_ids, gold_ids, strict=True):
        try:
            rank = ranked.index(gold) + 1
            total += 1.0 / rank
        except ValueError:
            total += 0.0
    return total / max(len(gold_ids), 1)


def pairwise_accuracy(chosen_scores: Sequence[float], rejected_scores: Sequence[float]) -> float:
    correct = sum(c > r for c, r in zip(chosen_scores, rejected_scores, strict=True))
    return correct / max(len(chosen_scores), 1)


def normalized_coordinate_error(
    predicted_point: tuple[float, float],
    target_point: tuple[float, float],
    screen_size: ScreenSize,
    predicted_space: str = "pixel",
    target_space: str = "pixel",
) -> float:
    pred_x, pred_y = point_to_pixel(predicted_point, screen_size, predicted_space)
    tgt_x, tgt_y = point_to_pixel(target_point, screen_size, target_space)
    diagonal = (screen_size.width**2 + screen_size.height**2) ** 0.5
    distance = ((pred_x - tgt_x) ** 2 + (pred_y - tgt_y) ** 2) ** 0.5
    return distance / diagonal


def distance_threshold_accuracy(
    predicted_points: Sequence[tuple[float, float]],
    target_points: Sequence[tuple[float, float]],
    screen_sizes: Sequence[ScreenSize],
    threshold_px: float = 50.0,
    predicted_space: str = "pixel",
    target_space: str = "pixel",
) -> float:
    hits = 0
    for predicted, target, screen_size in zip(
        predicted_points, target_points, screen_sizes, strict=True
    ):
        pred_x, pred_y = point_to_pixel(predicted, screen_size, predicted_space)
        tgt_x, tgt_y = point_to_pixel(target, screen_size, target_space)
        distance = ((pred_x - tgt_x) ** 2 + (pred_y - tgt_y) ** 2) ** 0.5
        hits += int(distance <= threshold_px)
    return hits / max(len(target_points), 1)


def point_in_box(
    point: tuple[float, float],
    bbox: BoundingBox,
    screen_size: ScreenSize,
    point_space: str = "pixel",
) -> bool:
    x, y = point_to_pixel(point, screen_size, point_space)
    pixel_bbox = bbox_to_pixel(bbox, screen_size)
    return pixel_bbox.x1 <= x <= pixel_bbox.x2 and pixel_bbox.y1 <= y <= pixel_bbox.y2


def click_accuracy(
    predicted_points: Sequence[tuple[float, float]],
    target_boxes: Sequence[BoundingBox],
    screen_sizes: Sequence[ScreenSize],
    predicted_space: str = "pixel",
) -> float:
    hits = 0
    for point, bbox, screen_size in zip(predicted_points, target_boxes, screen_sizes, strict=True):
        hits += int(point_in_box(point, bbox, screen_size, predicted_space))
    return hits / max(len(target_boxes), 1)
