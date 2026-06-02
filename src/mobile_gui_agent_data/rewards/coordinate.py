import math

from mobile_gui_agent_data.schemas import ActionType
from mobile_gui_agent_data.rewards.base import RewardContext, RewardFunction
from mobile_gui_agent_data.utils.coordinates import bbox_to_pixel, point_to_pixel


class CoordinateReward(RewardFunction):
    name = "coordinate"

    def __init__(self, tau_px: float = 80.0) -> None:
        self.tau_px = tau_px

    def __call__(self, context: RewardContext) -> float:
        if context.candidate.type not in {ActionType.CLICK, ActionType.SWIPE}:
            return 1.0

        pred = context.candidate.primary_point()
        if pred is None:
            return 0.0

        if context.step.target_bbox is not None and context.step.screen_size is not None:
            x, y = point_to_pixel(pred, context.step.screen_size, context.candidate.coordinate_space)
            bbox = bbox_to_pixel(context.step.target_bbox, context.step.screen_size)
            return 1.0 if bbox.x1 <= x <= bbox.x2 and bbox.y1 <= y <= bbox.y2 else 0.0

        if context.reference is None:
            return 0.0

        ref = context.reference.primary_point()
        if ref is None:
            return 0.0

        if context.step.screen_size is not None:
            pred = point_to_pixel(pred, context.step.screen_size, context.candidate.coordinate_space)
            ref = point_to_pixel(ref, context.step.screen_size, context.reference.coordinate_space)

        distance = math.dist(pred, ref)
        return float(math.exp(-distance / self.tau_px))
