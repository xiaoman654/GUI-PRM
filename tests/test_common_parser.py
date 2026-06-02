from mobile_gui_agent_data.datasets.common import is_aitw_tap, parse_action, parse_screen_size


def test_parse_string_click_action() -> None:
    action = parse_action("click(12, 34)")

    assert action.type == "click"
    assert action.point == (12.0, 34.0)


def test_parse_alias_action_dict() -> None:
    action = parse_action({"action_type": "tap", "x": 5, "y": 6})

    assert action.type == "click"
    assert action.point == (5.0, 6.0)


def test_parse_screen_size_aliases() -> None:
    screen_size = parse_screen_size({"image_width": 1080, "image_height": 2400})

    assert screen_size is not None
    assert screen_size.width == 1080


def test_aitw_tap_threshold() -> None:
    assert is_aitw_tap((0.5, 0.5), (0.52, 0.5))
    assert not is_aitw_tap((0.5, 0.5), (0.7, 0.5))
