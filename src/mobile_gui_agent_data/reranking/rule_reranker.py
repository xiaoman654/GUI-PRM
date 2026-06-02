from mobile_gui_agent_data.rewards.base import RewardContext
from mobile_gui_agent_data.rewards.hybrid import HybridReward
from mobile_gui_agent_data.schemas import GUIAction, StepSample


class RuleRewardReranker:
    def __init__(self, reward: HybridReward | None = None) -> None:
        self.reward = reward or HybridReward()

    def rank(self, step: StepSample, candidates: list[GUIAction]) -> list[tuple[GUIAction, float]]:
        scored = []
        for candidate in candidates:
            context = RewardContext(step=step, candidate=candidate, reference=step.action)
            scored.append((candidate, self.reward.score(context).total))
        return sorted(scored, key=lambda item: item[1], reverse=True)
