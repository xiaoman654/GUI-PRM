from mobile_gui_agent_data.datasets.registry import get_parser
from mobile_gui_agent_data.utils.io import read_records


def test_demo_episode_parser() -> None:
    parser = get_parser("aitw")
    episodes = list(read_records("examples/demo_episodes.jsonl"))
    steps = [step for episode in episodes for step in parser.parse(episode)]

    assert len(steps) == 5
    assert steps[0].episode_id == "demo_ep_001"
    assert steps[1].action.type == "type"
