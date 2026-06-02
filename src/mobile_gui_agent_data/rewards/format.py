from mobile_gui_agent_data.rewards.base import RewardContext, RewardFunction


class FormatReward(RewardFunction):
    name = "format"

    def __call__(self, context: RewardContext) -> float:
        action = context.candidate
        if action.type is None:
            return 0.0
        return 1.0
