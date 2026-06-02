from pydantic import BaseModel, Field

from mobile_gui_agent_data.schemas import GUIAction, StepSample


class RewardContext(BaseModel):
    step: StepSample
    candidate: GUIAction
    reference: GUIAction | None = None
    state_change_score: float | None = None
    metadata: dict = Field(default_factory=dict)


class RewardBreakdown(BaseModel):
    total: float
    components: dict[str, float] = Field(default_factory=dict)


class RewardFunction:
    name = "reward"

    def __call__(self, context: RewardContext) -> float:
        raise NotImplementedError
