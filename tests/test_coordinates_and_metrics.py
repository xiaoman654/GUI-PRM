from mobile_gui_agent_data.evaluation.metrics import (
    click_accuracy,
    distance_threshold_accuracy,
    normalized_coordinate_error,
)
from mobile_gui_agent_data.schemas import BoundingBox, ScreenSize
from mobile_gui_agent_data.utils.coordinates import point_from_pixel, point_to_pixel


def test_coordinate_conversion_round_trip() -> None:
    screen = ScreenSize(width=1080, height=2400)
    normalized = point_from_pixel((540, 1200), screen, "normalized_1000")
    assert normalized == (500.0, 500.0)
    assert point_to_pixel(normalized, screen, "normalized_1000") == (540.0, 1200.0)


def test_grounding_metrics() -> None:
    screen = ScreenSize(width=100, height=100)
    bbox = BoundingBox(x1=40, y1=40, x2=60, y2=60)

    assert click_accuracy([(50, 50)], [bbox], [screen]) == 1.0
    assert distance_threshold_accuracy([(52, 50)], [(50, 50)], [screen], 3) == 1.0
    assert normalized_coordinate_error((50, 50), (50, 50), screen) == 0.0
