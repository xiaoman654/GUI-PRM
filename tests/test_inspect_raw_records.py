from mobile_gui_agent_data.analysis.inspect import inspect_records


def test_inspect_records_reports_paths() -> None:
    report = inspect_records(
        [
            {
                "episode_id": "ep",
                "steps": [{"action": {"type": "click", "point": [1, 2]}}],
            }
        ]
    )

    assert report["top_level_keys"]["episode_id"] == 1
    assert "steps[]" in report["paths"]
    assert report["action_like_values"]["click"] == 1
