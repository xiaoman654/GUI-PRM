# UI-R1 Alignment Notes

UI-R1 is useful to this project as a reward-design and data-selection reference,
not as a GRPO/RL recipe to reproduce.

Adopted ideas:

1. Keep the first validation target as low-level GUI action prediction.
2. Decompose action reward into format, action type, and coordinate components.
3. Prefer point-based click reward over bbox IoU for GUI action evaluation.
4. Use bbox containment when a target box exists, and distance to human click
   when only a click point exists.
5. Treat data selection as Quality + Difficulty + Diversity rather than simply
   maximizing sample count.
6. Run reward-component ablations before assuming a larger hybrid reward is
   better.
7. Keep direct action JSON as the default output format for efficient execution;
   reasoning traces are optional analysis artifacts, not the default target.

Explicitly out of scope for the first version:

1. Reproducing UI-R1's GRPO training.
2. Matching UI-R1 benchmark numbers.
3. Treating 136 examples as a fixed target size.
4. Making long reasoning traces the primary output.

Project translation:

```text
UI-R1 rule reward
-> data audit rules
-> preference-pair scoring
-> rule-based reranking
-> optional lightweight scorer validation
```
