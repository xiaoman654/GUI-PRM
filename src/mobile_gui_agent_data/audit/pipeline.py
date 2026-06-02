from mobile_gui_agent_data.audit.rules import (
    AuditResult,
    check_action_type,
    check_coordinate_in_screen,
    check_instruction,
    check_text_input,
    quality_bucket,
)
from mobile_gui_agent_data.schemas import ActionType, StepSample


class AuditPipeline:
    def __init__(
        self,
        allowed_action_types: set[ActionType] | None = None,
        max_text_length: int = 256,
        high_threshold: float = 0.8,
        medium_threshold: float = 0.5,
    ) -> None:
        self.allowed_action_types = allowed_action_types or set(ActionType)
        self.max_text_length = max_text_length
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold

    def audit_step(self, step: StepSample) -> AuditResult:
        findings = [
            check_action_type(step.action, self.allowed_action_types),
            check_coordinate_in_screen(step),
            check_text_input(step.action, self.max_text_length),
            check_instruction(step),
        ]
        quality_score = sum(item.score for item in findings) / len(findings)
        return AuditResult(
            step_id=f"{step.episode_id}:{step.step_id}",
            quality_score=quality_score,
            quality_bucket=quality_bucket(quality_score, self.high_threshold, self.medium_threshold),
            findings=findings,
        )
