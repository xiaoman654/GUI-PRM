from mobile_gui_agent_data.scorer.dataset import scorer_records_from_pair
from mobile_gui_agent_data.schemas import GUIAction, PreferencePair, StepSample


def test_scorer_records_from_pair() -> None:
    step = StepSample(
        episode_id="ep",
        step_id=0,
        task="Click search",
        screenshot_before="image.png",
        action=GUIAction(type="click", point=(0.5, 0.5), coordinate_space="normalized_1"),
    )
    pair = PreferencePair(
        pair_id="pair",
        step=step,
        chosen=step.action,
        rejected=GUIAction(type="click", point=(0.1, 0.1), coordinate_space="normalized_1"),
        negative_type="random_coordinate",
    )

    records = scorer_records_from_pair(pair)

    assert len(records) == 2
    assert records[0]["label"] == "Yes"
    assert records[1]["label"] == "No"
    assert records[0]["image"] == "image.png"
