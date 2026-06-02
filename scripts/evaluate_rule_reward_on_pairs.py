import argparse
import json
from collections import defaultdict

from mobile_gui_agent_data.rewards.base import RewardContext
from mobile_gui_agent_data.rewards.presets import action_prediction_reward, grounding_reward
from mobile_gui_agent_data.schemas import PreferencePair
from mobile_gui_agent_data.utils.io import read_jsonl


REWARD_PRESETS = {
    "action_prediction": action_prediction_reward,
    "grounding": grounding_reward,
}


def summarize(scores: list[tuple[float, float]]) -> dict:
    if not scores:
        return {
            "count": 0,
            "pairwise_accuracy": None,
            "tie_rate": None,
            "mean_margin": None,
        }
    correct = sum(chosen > rejected for chosen, rejected in scores)
    ties = sum(chosen == rejected for chosen, rejected in scores)
    margins = [chosen - rejected for chosen, rejected in scores]
    return {
        "count": len(scores),
        "pairwise_accuracy": correct / len(scores),
        "tie_rate": ties / len(scores),
        "mean_margin": sum(margins) / len(margins),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Preference pair JSONL")
    parser.add_argument("--output", required=True)
    parser.add_argument("--preset", default="action_prediction", choices=sorted(REWARD_PRESETS))
    args = parser.parse_args()

    reward = REWARD_PRESETS[args.preset]()
    all_scores = []
    by_negative_type: dict[str, list[tuple[float, float]]] = defaultdict(list)
    component_margins: dict[str, list[float]] = defaultdict(list)

    for raw in read_jsonl(args.input):
        pair = PreferencePair(**raw)
        chosen_breakdown = reward.score(
            RewardContext(step=pair.step, candidate=pair.chosen, reference=pair.step.action)
        )
        rejected_breakdown = reward.score(
            RewardContext(step=pair.step, candidate=pair.rejected, reference=pair.step.action)
        )
        score_pair = (chosen_breakdown.total, rejected_breakdown.total)
        all_scores.append(score_pair)
        by_negative_type[pair.negative_type].append(score_pair)

        for name, chosen_value in chosen_breakdown.components.items():
            rejected_value = rejected_breakdown.components.get(name, 0.0)
            component_margins[name].append(chosen_value - rejected_value)

    report = {
        "preset": args.preset,
        "overall": summarize(all_scores),
        "by_negative_type": {
            negative_type: summarize(scores)
            for negative_type, scores in sorted(by_negative_type.items())
        },
        "component_mean_margins": {
            name: sum(values) / len(values)
            for name, values in sorted(component_margins.items())
            if values
        },
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
