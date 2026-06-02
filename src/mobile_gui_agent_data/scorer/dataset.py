from typing import Any

from mobile_gui_agent_data.schemas import PreferencePair


def action_to_text(action: dict[str, Any]) -> str:
    action_type = action.get("type")
    if action_type == "click":
        return f"click(point={action.get('point')})"
    if action_type == "swipe":
        return f"swipe(start_point={action.get('start_point')}, end_point={action.get('end_point')})"
    if action_type == "type":
        return f"type(text={action.get('text')!r})"
    if action_type in {"back", "home", "wait", "finish", "impossible"}:
        return str(action_type)
    return str(action)


def scorer_records_from_pair(pair: PreferencePair) -> list[dict[str, Any]]:
    base = {
        "pair_id": pair.pair_id,
        "episode_id": pair.step.episode_id,
        "step_id": pair.step.step_id,
        "image": pair.step.screenshot_before,
        "instruction": pair.step.task,
        "screen_size": pair.step.screen_size.model_dump(mode="json") if pair.step.screen_size else None,
        "negative_type": pair.negative_type,
    }
    chosen = pair.chosen.model_dump(mode="json")
    rejected = pair.rejected.model_dump(mode="json")
    return [
        {
            **base,
            "sample_id": f"{pair.pair_id}:chosen",
            "candidate_action": chosen,
            "candidate_action_text": action_to_text(chosen),
            "label": "Yes",
            "label_id": 1,
        },
        {
            **base,
            "sample_id": f"{pair.pair_id}:rejected",
            "candidate_action": rejected,
            "candidate_action_text": action_to_text(rejected),
            "label": "No",
            "label_id": 0,
        },
    ]
