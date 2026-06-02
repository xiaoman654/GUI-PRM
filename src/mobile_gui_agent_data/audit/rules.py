from pydantic import BaseModel, Field

from mobile_gui_agent_data.schemas import ActionType, GUIAction, StepSample
from mobile_gui_agent_data.utils.coordinates import point_to_pixel


class AuditFinding(BaseModel):
    rule: str
    passed: bool
    score: float
    message: str = ""


class AuditResult(BaseModel):
    step_id: str
    quality_score: float
    quality_bucket: str
    findings: list[AuditFinding] = Field(default_factory=list)


def check_action_type(action: GUIAction, allowed: set[ActionType]) -> AuditFinding:
    passed = action.type in allowed
    return AuditFinding(
        rule="action_type",
        passed=passed,
        score=1.0 if passed else 0.0,
        message="" if passed else f"Unsupported action type: {action.type}",
    )


def check_coordinate_in_screen(step: StepSample) -> AuditFinding:
    point = step.action.primary_point()
    if point is None or step.screen_size is None:
        return AuditFinding(rule="coordinate", passed=True, score=1.0)

    x, y = point_to_pixel(point, step.screen_size, step.action.coordinate_space)
    passed = 0 <= x < step.screen_size.width and 0 <= y < step.screen_size.height
    return AuditFinding(
        rule="coordinate",
        passed=passed,
        score=1.0 if passed else 0.0,
        message="" if passed else f"Point {point} is outside {step.screen_size.width}x{step.screen_size.height}",
    )


def check_text_input(action: GUIAction, max_length: int) -> AuditFinding:
    if action.type != ActionType.TYPE:
        return AuditFinding(rule="text_input", passed=True, score=1.0)

    text = action.text or ""
    passed = bool(text.strip()) and len(text) <= max_length
    return AuditFinding(
        rule="text_input",
        passed=passed,
        score=1.0 if passed else 0.0,
        message="" if passed else "Empty or overly long type action text",
    )


def check_instruction(step: StepSample) -> AuditFinding:
    passed = len(step.task.strip()) >= 3
    return AuditFinding(
        rule="instruction",
        passed=passed,
        score=1.0 if passed else 0.0,
        message="" if passed else "Instruction is empty or too short",
    )


def quality_bucket(score: float, high_threshold: float = 0.8, medium_threshold: float = 0.5) -> str:
    if score >= high_threshold:
        return "high"
    if score >= medium_threshold:
        return "medium"
    return "low"
