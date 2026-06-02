from mobile_gui_agent_data.preference.negative_sampling import (
    random_coordinate_negative,
    shifted_coordinate_negative,
)
from mobile_gui_agent_data.schemas import GUIAction, ScreenSize, StepSample


def test_negative_sampling_preserves_normalized_coordinate_space() -> None:
    step = StepSample(
        episode_id="ep",
        step_id=0,
        task="Click",
        screen_size=ScreenSize(width=100, height=200),
        action=GUIAction(type="click", point=(0.5, 0.5), coordinate_space="normalized_1"),
    )

    random_negative = random_coordinate_negative(step)
    shifted_negative = shifted_coordinate_negative(step, offset_px=10)

    assert random_negative.coordinate_space == "normalized_1"
    assert 0.0 <= random_negative.point[0] <= 1.0
    assert 0.0 <= random_negative.point[1] <= 1.0
    assert shifted_negative.coordinate_space == "normalized_1"
    assert shifted_negative.point == (0.6, 0.55)
