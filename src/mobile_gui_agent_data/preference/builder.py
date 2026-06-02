from collections.abc import Iterable

from mobile_gui_agent_data.preference.negative_sampling import NEGATIVE_SAMPLERS
from mobile_gui_agent_data.schemas import PreferencePair, StepSample


class PreferenceBuilder:
    def __init__(self, strategies: list[str] | None = None, negatives_per_step: int = 4) -> None:
        self.strategies = strategies or list(NEGATIVE_SAMPLERS)
        self.negatives_per_step = negatives_per_step

    def build_for_step(self, step: StepSample) -> list[PreferencePair]:
        pairs = []
        selected = self.strategies[: self.negatives_per_step]
        for strategy in selected:
            rejected = NEGATIVE_SAMPLERS[strategy](step)
            pairs.append(
                PreferencePair(
                    pair_id=f"{step.episode_id}:{step.step_id}:{strategy}",
                    step=step,
                    chosen=step.action,
                    rejected=rejected,
                    negative_type=strategy,
                )
            )
        return pairs

    def build(self, steps: Iterable[StepSample]) -> Iterable[PreferencePair]:
        for step in steps:
            yield from self.build_for_step(step)
