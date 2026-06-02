from mobile_gui_agent_data.rewards.action_type import ActionTypeReward
from mobile_gui_agent_data.rewards.coordinate import CoordinateReward
from mobile_gui_agent_data.rewards.format import FormatReward
from mobile_gui_agent_data.rewards.hybrid import HybridReward
from mobile_gui_agent_data.rewards.state_change import StateChangeReward
from mobile_gui_agent_data.rewards.text import TextInputReward


def grounding_reward() -> HybridReward:
    return HybridReward(
        rewards=[FormatReward(), CoordinateReward()],
        weights={"format": 0.25, "coordinate": 1.0},
    )


def action_prediction_reward() -> HybridReward:
    return HybridReward(
        rewards=[FormatReward(), ActionTypeReward(), CoordinateReward(), TextInputReward()],
        weights={"format": 0.5, "action_type": 1.0, "coordinate": 1.0, "text": 1.0},
    )


def full_audit_reward() -> HybridReward:
    return HybridReward(
        rewards=[
            FormatReward(),
            ActionTypeReward(),
            CoordinateReward(),
            TextInputReward(),
            StateChangeReward(),
        ],
        weights={
            "format": 0.5,
            "action_type": 1.0,
            "coordinate": 1.0,
            "text": 1.0,
            "state_change": 0.5,
        },
    )
