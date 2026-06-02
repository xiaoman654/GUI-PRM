from mobile_gui_agent_data.rewards.base import RewardContext, RewardFunction


class ActionTypeReward(RewardFunction):
    name = "action_type"

    def __call__(self, context: RewardContext) -> float:
        if context.reference is None:
            return 0.0
        return 1.0 if context.candidate.type == context.reference.type else 0.0
