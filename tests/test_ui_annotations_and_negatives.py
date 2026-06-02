from mobile_gui_agent_data.datasets.common import parse_aitw_ui_elements
from mobile_gui_agent_data.preference.negative_sampling import same_screen_element_negative
from mobile_gui_agent_data.schemas import GUIAction, ScreenSize, StepSample
from mobile_gui_agent_data.utils.ui_elements import element_containing_action_point


def test_parse_aitw_ui_elements_flat_positions() -> None:
    elements = parse_aitw_ui_elements(
        {
            "image_ui_annotations_positions": [0.5, 0.5, 0.2, 0.4],
            "image_ui_annotations_text": ["Search"],
            "image_ui_annotations_ui_types": ["TEXT"],
        }
    )

    assert len(elements) == 1
    assert elements[0].bbox.x1 == 0.3
    assert elements[0].bbox.y1 == 0.4
    assert elements[0].text == "Search"


def test_same_screen_element_negative_uses_other_element() -> None:
    elements = parse_aitw_ui_elements(
        {
            "image_ui_annotations_positions": [
                0.5,
                0.2,
                0.2,
                0.2,
                0.5,
                0.8,
                0.2,
                0.2,
            ],
            "image_ui_annotations_text": ["A", "B"],
            "image_ui_annotations_ui_types": ["TEXT", "TEXT"],
        }
    )
    step = StepSample(
        episode_id="ep",
        step_id=0,
        task="Click A",
        screen_size=ScreenSize(width=100, height=100),
        action=GUIAction(type="click", point=(0.2, 0.5), coordinate_space="normalized_1"),
        ui_elements=elements,
    )

    source = element_containing_action_point(step)
    negative = same_screen_element_negative(step)
    negative_step = step.model_copy(update={"action": negative})
    target = element_containing_action_point(negative_step)

    assert source is not None
    assert target is not None
    assert source.index != target.index
