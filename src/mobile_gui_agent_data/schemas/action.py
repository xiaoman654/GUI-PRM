from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    SWIPE = "swipe"
    BACK = "back"
    HOME = "home"
    WAIT = "wait"
    FINISH = "finish"
    IMPOSSIBLE = "impossible"


class ScreenSize(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    coordinate_space: Literal["pixel", "normalized_1000", "normalized_1"] = "pixel"


class UIElement(BaseModel):
    bbox: BoundingBox
    text: str = ""
    ui_type: str = ""
    index: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GUIAction(BaseModel):
    type: ActionType
    point: tuple[float, float] | None = None
    start_point: tuple[float, float] | None = None
    end_point: tuple[float, float] | None = None
    text: str | None = None
    direction: str | None = None
    coordinate_space: Literal["pixel", "normalized_1000", "normalized_1"] = "pixel"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def primary_point(self) -> tuple[float, float] | None:
        if self.point is not None:
            return self.point
        if self.start_point is not None:
            return self.start_point
        return None


class StepSample(BaseModel):
    episode_id: str
    step_id: int = Field(ge=0)
    task: str
    screenshot_before: str | None = None
    screenshot_after: str | None = None
    screen_size: ScreenSize | None = None
    action: GUIAction
    target_bbox: BoundingBox | None = None
    ui_elements: list[UIElement] = Field(default_factory=list)
    history: list[GUIAction] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PreferencePair(BaseModel):
    pair_id: str
    step: StepSample
    chosen: GUIAction
    rejected: GUIAction
    negative_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
