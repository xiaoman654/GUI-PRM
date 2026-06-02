# SeeClick Alignment Notes

SeeClick is useful to this project mainly as a methodological reference, not as
a training recipe to reproduce.

Adopted ideas:

1. Treat GUI grounding as a core bottleneck for visual GUI agents.
2. Keep `screenshot + instruction -> click point / action` as the main data form.
3. Support normalized coordinates, especially `[0, 1000]`, while preserving raw
   pixel coordinates for execution.
4. Prefer point-level action evaluation before introducing full bounding-box
   detection.
5. Add click-oriented metrics: point-in-box accuracy, distance-threshold
   accuracy, and normalized coordinate error.
6. Use instruction-wise train/validation/test split to reduce leakage across
   repeated or near-duplicate tasks.
7. Keep the first action space small: click, type, scroll/swipe, back, home,
   wait, finish.

Explicitly out of scope for this project:

1. Reproducing SeeClick's GUI grounding pre-training.
2. Rebuilding ScreenSpot.
3. Training a large Qwen-VL-scale GUI agent as the primary deliverable.
4. Covering mobile, desktop, and web equally in the first version.

The project focus remains: data audit, reward design, preference construction,
reranking, and evaluation for mobile GUI agent action quality.
