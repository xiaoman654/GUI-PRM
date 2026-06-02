from mobile_gui_agent_data.datasets.aitw import AITWParser
from mobile_gui_agent_data.datasets.android_control import AndroidControlParser
from mobile_gui_agent_data.datasets.base import EpisodeParser


PARSERS: dict[str, type[EpisodeParser]] = {
    "aitw": AITWParser,
    "android_control": AndroidControlParser,
}


def get_parser(source: str) -> EpisodeParser:
    try:
        return PARSERS[source]()
    except KeyError as exc:
        available = ", ".join(sorted(PARSERS))
        raise ValueError(f"Unknown source '{source}'. Available sources: {available}") from exc
