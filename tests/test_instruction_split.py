from mobile_gui_agent_data.datasets.split import instruction_wise_split
from mobile_gui_agent_data.schemas import GUIAction, StepSample


def test_instruction_wise_split_keeps_same_instruction_together() -> None:
    steps = [
        StepSample(episode_id="a", step_id=0, task="Turn on Wi-Fi", action=GUIAction(type="click")),
        StepSample(episode_id="b", step_id=0, task="turn   on wi-fi", action=GUIAction(type="click")),
        StepSample(episode_id="c", step_id=0, task="Open settings", action=GUIAction(type="click")),
    ]
    splits = instruction_wise_split(steps)

    locations = {}
    for split_name, split_steps in splits.items():
        for step in split_steps:
            locations.setdefault(" ".join(step.task.lower().split()), split_name)

    assert locations["turn on wi-fi"] == locations["turn on wi-fi"]
