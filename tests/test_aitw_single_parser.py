from mobile_gui_agent_data.datasets.aitw import AITWParser


def test_parse_hf_aitw_single_step_row() -> None:
    row = {
        "ep_id": "episode-a",
        "step_id": 0,
        "goal_info": "search ebay",
        "image_encoded": {"type": "PIL.Image", "size": [720, 1520], "mode": "RGB"},
        "results_action_type": 4,
        "results_yx_touch": [0.25, 0.75],
        "results_yx_lift": [0.25, 0.75],
    }

    steps = list(AITWParser().parse(row))

    assert len(steps) == 1
    assert steps[0].episode_id == "episode-a"
    assert steps[0].screen_size is not None
    assert steps[0].screen_size.width == 720
    assert steps[0].action.type == "click"
    assert steps[0].action.point == (0.75, 0.25)
    assert steps[0].action.coordinate_space == "normalized_1"


def test_parse_hf_aitw_type_action() -> None:
    row = {
        "ep_id": "episode-a",
        "step_id": 1,
        "goal_info": "search ebay",
        "image_encoded": {"size": [720, 1520]},
        "results_action_type": 3,
        "results_type_action": ["hello"],
    }

    step = list(AITWParser().parse(row))[0]

    assert step.action.type == "type"
    assert step.action.text == "hello"
