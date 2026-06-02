from collections.abc import Iterable

from mobile_gui_agent_data.datasets.base import EpisodeParser
from mobile_gui_agent_data.datasets.common import (
    first_present,
    get_episode_steps,
    get_screenshot_after,
    get_screenshot_before,
    parse_action,
    parse_aitw_action,
    parse_aitw_ui_elements,
    parse_bbox,
    parse_screen_size,
)
from mobile_gui_agent_data.schemas import StepSample


class AITWParser(EpisodeParser):
    source_name = "aitw"

    def parse(self, raw_episode: dict) -> Iterable[StepSample]:
        episode_id = str(first_present(raw_episode, ["episode_id", "ep_id", "id"], "unknown"))
        task = first_present(raw_episode, ["task", "instruction", "goal", "goal_info", "query"], "")
        screen_size = parse_screen_size(raw_episode)

        for idx, raw_step in enumerate(get_episode_steps(raw_episode)):
            action_payload = first_present(raw_step, ["action", "target_action", "operation"], {})
            action = parse_aitw_action(raw_step) or parse_action(action_payload)
            yield StepSample(
                episode_id=episode_id,
                step_id=int(raw_step.get("step_id", idx)),
                task=first_present(raw_step, ["task", "instruction", "goal", "goal_info"], task),
                screenshot_before=get_screenshot_before(raw_step),
                screenshot_after=get_screenshot_after(raw_step),
                screen_size=parse_screen_size(raw_step) or screen_size,
                action=action,
                target_bbox=parse_bbox(first_present(raw_step, ["target_bbox", "bbox", "box"])),
                ui_elements=parse_aitw_ui_elements(raw_step),
                metadata={
                    "source": self.source_name,
                    "current_activity": raw_step.get("current_activity"),
                    "device_type": raw_step.get("device_type"),
                    "episode_length": raw_step.get("episode_length"),
                },
            )
