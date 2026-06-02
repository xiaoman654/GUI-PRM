from mobile_gui_agent_data.rewards.base import RewardContext, RewardFunction


class StateChangeReward(RewardFunction):
    name = "state_change"

    def __init__(self, threshold: float = 0.01) -> None:
        self.threshold = threshold

    def __call__(self, context: RewardContext) -> float:
        if context.state_change_score is None:
            return 0.0
        return 1.0 if context.state_change_score >= self.threshold else 0.0
