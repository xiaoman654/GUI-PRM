from rapidfuzz.distance import Levenshtein

from mobile_gui_agent_data.schemas import ActionType
from mobile_gui_agent_data.rewards.base import RewardContext, RewardFunction


class TextInputReward(RewardFunction):
    name = "text"

    def __call__(self, context: RewardContext) -> float:
        if context.reference is None:
            return 0.0
        if context.candidate.type != ActionType.TYPE:
            return 1.0

        pred = context.candidate.text or ""
        ref = context.reference.text or ""
        if not pred or not ref:
            return 0.0
        return float(Levenshtein.normalized_similarity(pred, ref))
