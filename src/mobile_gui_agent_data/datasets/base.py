from collections.abc import Iterable

from mobile_gui_agent_data.schemas import StepSample


class EpisodeParser:
    """Base interface for converting raw GUI episodes into step-level samples."""

    source_name: str = "unknown"

    def parse(self, raw_episode: dict) -> Iterable[StepSample]:
        raise NotImplementedError
