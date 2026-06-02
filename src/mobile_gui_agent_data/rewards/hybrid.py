from mobile_gui_agent_data.rewards.action_type import ActionTypeReward
from mobile_gui_agent_data.rewards.base import RewardBreakdown, RewardContext, RewardFunction
from mobile_gui_agent_data.rewards.coordinate import CoordinateReward
from mobile_gui_agent_data.rewards.format import FormatReward
from mobile_gui_agent_data.rewards.state_change import StateChangeReward
from mobile_gui_agent_data.rewards.text import TextInputReward


class HybridReward:
    def __init__(self, rewards: list[RewardFunction] | None = None, weights: dict[str, float] | None = None) -> None:
        self.rewards = rewards or [
            FormatReward(),
            ActionTypeReward(),
            CoordinateReward(),
            TextInputReward(),
            StateChangeReward(),
        ]
        self.weights = weights or {reward.name: 1.0 for reward in self.rewards}

    def score(self, context: RewardContext) -> RewardBreakdown:
        components = {reward.name: reward(context) for reward in self.rewards}
        weighted_sum = sum(components[name] * self.weights.get(name, 1.0) for name in components)
        normalizer = sum(self.weights.get(name, 1.0) for name in components) or 1.0
        return RewardBreakdown(total=weighted_sum / normalizer, components=components)
