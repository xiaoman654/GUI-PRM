from mobile_gui_agent_data.schemas import StepSample
from mobile_gui_agent_data.utils.coordinates import (
    action_to_coordinate_space,
    bbox_to_coordinate_space,
)


def step_to_coordinate_space(
    step: StepSample,
    coordinate_space: str = "normalized_1000",
) -> StepSample:
    if step.screen_size is None:
        return step

    action = action_to_coordinate_space(step.action, step.screen_size, coordinate_space)
    history = [
        action_to_coordinate_space(action_item, step.screen_size, coordinate_space)
        for action_item in step.history
    ]
    target_bbox = (
        bbox_to_coordinate_space(step.target_bbox, step.screen_size, coordinate_space)
        if step.target_bbox is not None
        else None
    )
    return step.model_copy(update={"action": action, "history": history, "target_bbox": target_bbox})
