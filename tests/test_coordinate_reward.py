from mobile_gui_agent_data.rewards.base import RewardContext
from mobile_gui_agent_data.rewards.coordinate import CoordinateReward
from mobile_gui_agent_data.schemas import BoundingBox, GUIAction, ScreenSize, StepSample


def test_coordinate_reward_uses_target_bbox_when_available() -> None:
    step = StepSample(
        episode_id="ep",
        step_id=0,
        task="Click button",
        screen_size=ScreenSize(width=100, height=100),
        action=GUIAction(type="click", point=(50, 50)),
        target_bbox=BoundingBox(x1=40, y1=40, x2=60, y2=60),
    )

    reward = CoordinateReward()

    inside = reward(
        RewardContext(step=step, candidate=GUIAction(type="click", point=(50, 50)))
    )
    outside = reward(
        RewardContext(step=step, candidate=GUIAction(type="click", point=(80, 80)))
    )

    assert inside == 1.0
    assert outside == 0.0


def test_coordinate_reward_converts_coordinate_spaces_before_distance() -> None:
    step = StepSample(
        episode_id="ep",
        step_id=0,
        task="Click button",
        screen_size=ScreenSize(width=100, height=200),
        action=GUIAction(type="click", point=(0.5, 0.5), coordinate_space="normalized_1"),
    )

    score = CoordinateReward()(
        RewardContext(
            step=step,
            candidate=GUIAction(type="click", point=(50, 100), coordinate_space="pixel"),
            reference=step.action,
        )
    )

    assert score == 1.0
