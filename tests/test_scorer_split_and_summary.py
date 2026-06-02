from mobile_gui_agent_data.scorer.split import instruction_wise_split_records
from mobile_gui_agent_data.scorer.summary import summarize_scorer_records


def test_instruction_wise_split_records_keeps_instruction_together() -> None:
    records = [
        {"instruction": "Open Settings", "sample_id": "a"},
        {"instruction": "open   settings", "sample_id": "b"},
        {"instruction": "Search Amazon", "sample_id": "c"},
    ]

    splits = instruction_wise_split_records(records)
    locations = {}
    for split_name, split_records in splits.items():
        for record in split_records:
            key = " ".join(record["instruction"].lower().split())
            locations.setdefault(key, split_name)
            assert locations[key] == split_name


def test_summarize_scorer_records() -> None:
    records = [
        {
            "label": "Yes",
            "instruction": "Click search",
            "episode_id": "ep",
            "image": "image.png",
            "candidate_action": {"type": "click"},
        },
        {
            "label": "No",
            "negative_type": "same_screen_element",
            "instruction": "Click search",
            "episode_id": "ep",
            "image": "image.png",
            "candidate_action": {"type": "click"},
        },
    ]

    summary = summarize_scorer_records(records)

    assert summary["num_records"] == 2
    assert summary["labels"] == {"Yes": 1, "No": 1}
    assert summary["negative_types"] == {"same_screen_element": 1}
