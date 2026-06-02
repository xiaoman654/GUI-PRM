import argparse

from mobile_gui_agent_data.reranking.rule_reranker import RuleRewardReranker
from mobile_gui_agent_data.schemas import GUIAction, StepSample
from mobile_gui_agent_data.utils.io import read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSONL with fields: step, candidates")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    reranker = RuleRewardReranker()

    def records():
        for raw in read_jsonl(args.input):
            step = StepSample(**raw["step"])
            candidates = [GUIAction(**item) for item in raw["candidates"]]
            ranked = reranker.rank(step, candidates)
            yield {
                "step_id": f"{step.episode_id}:{step.step_id}",
                "ranked": [
                    {"action": action.model_dump(mode="json"), "score": score}
                    for action, score in ranked
                ],
            }

    write_jsonl(args.output, records())


if __name__ == "__main__":
    main()
