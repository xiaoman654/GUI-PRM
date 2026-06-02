from mobile_gui_agent_data.analysis.stats import summarize_steps
from mobile_gui_agent_data.datasets.transforms import step_to_coordinate_space
from mobile_gui_agent_data.schemas import GUIAction, ScreenSize, StepSample


def test_step_coordinate_normalization() -> None:
    step = StepSample(
        episode_id="ep",
        step_id=0,
        task="Click center",
        screen_size=ScreenSize(width=100, height=200),
        action=GUIAction(type="click", point=(50, 100)),
    )

    normalized = step_to_coordinate_space(step)

    assert normalized.action.coordinate_space == "normalized_1000"
    assert normalized.action.point == (500.0, 500.0)


def test_summarize_steps() -> None:
    steps = [
        StepSample(
            episode_id="ep",
            step_id=0,
            task="Click center",
            screen_size=ScreenSize(width=100, height=200),
            action=GUIAction(type="click", point=(50, 100)),
        ),
        StepSample(
            episode_id="ep",
            step_id=1,
            task="Click center",
            screen_size=ScreenSize(width=100, height=200),
            action=GUIAction(type="type", text=""),
        ),
    ]

    summary = summarize_steps(steps)

    assert summary["num_steps"] == 2
    assert summary["action_counts"]["click"] == 1
    assert summary["text_input"]["empty_type_actions"] == 1
