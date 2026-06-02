from mobile_gui_agent_data.audit.pipeline import AuditPipeline
from mobile_gui_agent_data.preference.builder import PreferenceBuilder
from mobile_gui_agent_data.schemas import GUIAction, ScreenSize, StepSample


def test_audit_and_preference_smoke() -> None:
    step = StepSample(
        episode_id="ep1",
        step_id=0,
        task="Search nearby pizza",
        screen_size=ScreenSize(width=1080, height=2400),
        action=GUIAction(type="click", point=(500, 800)),
    )

    result = AuditPipeline().audit_step(step)
    assert result.quality_bucket == "high"

    pairs = PreferenceBuilder(negatives_per_step=2).build_for_step(step)
    assert len(pairs) == 2
    assert pairs[0].chosen.type == "click"
