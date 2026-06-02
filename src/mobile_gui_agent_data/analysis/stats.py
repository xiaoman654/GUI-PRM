from collections import Counter, defaultdict
from collections.abc import Iterable
from statistics import mean

from mobile_gui_agent_data.schemas import ActionType, StepSample
from mobile_gui_agent_data.utils.coordinates import point_to_pixel


def summarize_steps(steps: Iterable[StepSample]) -> dict:
    step_list = list(steps)
    action_counts = Counter(step.action.type.value for step in step_list)
    episode_lengths = Counter(step.episode_id for step in step_list)
    task_counts = Counter(step.task for step in step_list)

    point_actions = [
        step for step in step_list if step.action.primary_point() is not None and step.screen_size is not None
    ]
    out_of_bounds = 0
    normalized_x = []
    normalized_y = []
    for step in point_actions:
        point = step.action.primary_point()
        if point is None or step.screen_size is None:
            continue
        x, y = point_to_pixel(point, step.screen_size, step.action.coordinate_space)
        if not (0 <= x < step.screen_size.width and 0 <= y < step.screen_size.height):
            out_of_bounds += 1
        normalized_x.append(x / step.screen_size.width)
        normalized_y.append(y / step.screen_size.height)

    type_steps = [step for step in step_list if step.action.type == ActionType.TYPE]
    empty_type_steps = [step for step in type_steps if not (step.action.text or "").strip()]

    by_episode = defaultdict(list)
    for step in step_list:
        by_episode[step.episode_id].append(step.step_id)

    lengths = list(episode_lengths.values())
    return {
        "num_steps": len(step_list),
        "num_episodes": len(episode_lengths),
        "num_unique_tasks": len(task_counts),
        "action_counts": dict(action_counts),
        "episode_length": {
            "min": min(lengths) if lengths else 0,
            "max": max(lengths) if lengths else 0,
            "mean": mean(lengths) if lengths else 0,
        },
        "coordinate": {
            "num_point_actions": len(point_actions),
            "out_of_bounds": out_of_bounds,
            "out_of_bounds_rate": out_of_bounds / max(len(point_actions), 1),
            "mean_x_norm": mean(normalized_x) if normalized_x else None,
            "mean_y_norm": mean(normalized_y) if normalized_y else None,
        },
        "text_input": {
            "num_type_actions": len(type_steps),
            "empty_type_actions": len(empty_type_steps),
            "empty_type_rate": len(empty_type_steps) / max(len(type_steps), 1),
        },
    }
