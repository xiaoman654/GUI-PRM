from mobile_gui_agent_data.datasets.selection import select_quality_difficulty_diversity


def test_qdd_selection_filters_quality_and_balances_actions() -> None:
    records = [
        {
            "episode_id": "a",
            "step_id": 0,
            "action": {"type": "click"},
            "audit": {"quality_bucket": "high", "quality_score": 1.0},
            "metadata": {"difficulty_score": 0.2},
        },
        {
            "episode_id": "b",
            "step_id": 0,
            "action": {"type": "type"},
            "audit": {"quality_bucket": "high", "quality_score": 1.0},
            "metadata": {"difficulty_score": 0.9},
        },
        {
            "episode_id": "c",
            "step_id": 0,
            "action": {"type": "click"},
            "audit": {"quality_bucket": "low", "quality_score": 0.1},
            "metadata": {"difficulty_score": 1.0},
        },
    ]

    selected = select_quality_difficulty_diversity(records, max_samples=2)

    assert len(selected) == 2
    assert {record["action"]["type"] for record in selected} == {"click", "type"}
