from collections.abc import Iterable

from mobile_gui_agent_data.datasets.base import EpisodeParser
from mobile_gui_agent_data.datasets.common import (
    first_present,
    get_episode_steps,
    get_screenshot_after,
    get_screenshot_before,
    parse_action,
    parse_bbox,
    parse_screen_size,
)
from mobile_gui_agent_data.schemas import StepSample


class AndroidControlParser(EpisodeParser):
    source_name = "android_control"

    def parse(self, raw_episode: dict) -> Iterable[StepSample]:
        episode_id = str(raw_episode.get("episode_id", raw_episode.get("id", "unknown")))
        task = first_present(raw_episode, ["high_level_instruction", "task", "instruction", "goal"], "")
        screen_size = parse_screen_size(raw_episode)

        for idx, raw_step in enumerate(get_episode_steps(raw_episode)):
            action_payload = first_present(raw_step, ["action", "target_action", "operation"], {})
            step_task = first_present(raw_step, ["low_level_instruction", "task", "instruction"], task)
            yield StepSample(
                episode_id=episode_id,
                step_id=int(raw_step.get("step_id", idx)),
                task=step_task,
                screenshot_before=get_screenshot_before(raw_step),
                screenshot_after=get_screenshot_after(raw_step),
                screen_size=screen_size,
                action=parse_action(action_payload),
                target_bbox=parse_bbox(first_present(raw_step, ["target_bbox", "bbox", "box"])),
                metadata={"source": self.source_name, "high_level_instruction": task},
            )
