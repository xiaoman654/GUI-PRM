# V1/V2 Scorer Badcase Report

## 1. Current Goal

This project is currently a **Mobile GUI action scorer data experiment**, not a full online PRM system.

The scorer receives:

```text
screenshot + task instruction + candidate action
```

and predicts:

```text
Yes / No
```

The purpose of the current stage is to understand whether the way we construct negative actions is reliable enough for training a GUI action verifier.

## 2. V1 Baseline

V1 used four coarse negative strategies:

```text
random_coordinate
same_screen_element
shifted_coordinate
wrong_action_type
```

V1 test result:

| Metric | Value |
| --- | ---: |
| Accuracy | 94.00% |
| No->Yes false positives | 45 |
| Yes->No false negatives | 16 |
| shifted_coordinate accuracy | 75.59% |
| swipe accuracy | 80.00% |

The main issue was that the scorer often accepted negative actions, especially `shifted_coordinate` negatives.

## 3. V2 Data Changes

V2 made negative construction more action-aware and UI-aware:

| V1 idea | V2 subtype |
| --- | --- |
| random coordinate | `random_non_ui_point` |
| same screen element | `wrong_ui_element` |
| click coordinate shift | `near_miss_non_ui_shift` |
| swipe coordinate shift | `wrong_swipe_direction` |
| wrong action type | `click_to_type`, `swipe_to_click`, etc. |

V2 also filtered invalid zero-area UI boxes and strengthened the prompt around exact action verification.

V2 test result:

| Metric | Value |
| --- | ---: |
| Accuracy | 92.52% |
| No->Yes false positives | 52 |
| Yes->No false negatives | 24 |
| shifted_coordinate accuracy | 79.53% |
| same_screen_element accuracy | 85.83% |
| wrong_swipe_direction accuracy | 0.00% |

V2 improved some clean negative construction, but overall performance did not improve. This made the false positives more useful as a diagnostic set.

## 4. Manual Review Taxonomy

After reviewing the V2 `No->Yes` badcases, we consolidate the error causes into four main categories.

### 4.1 `negative_construction_error`

The constructed negative action is actually correct, equivalent, or very likely to complete the same GUI transition.

This includes what we previously called:

```text
label_noise
same_functional_region
```

Examples:

```text
Clicking a product image vs clicking the product title.
Clicking another point in the same search suggestion row.
Clicking button text vs clicking the same button's background area.
Clicking another point inside the same search/result card.
```

These should not be used as strong `No` labels.

Recommended treatment:

```text
delete
or relabel as Yes
or mark as weak/ambiguous and exclude from strong supervision
```

### 4.2 `ambiguous_or_uncertain`

The action is not clearly correct or incorrect from the available offline information.

Examples:

```text
Swipe or scroll actions judged from only one screenshot.
Captcha or permission-dialog actions without a low-level subgoal.
Actions in a multi-step task where history is needed to know the current stage.
Clicking a related product where alternative paths may exist.
```

These are not necessarily label errors, but the current data does not provide enough evidence to force a `No` label.

Recommended treatment:

```text
filter for now
or require next screenshot / execution feedback / history before labeling
```

### 4.3 `clean_model_error`

The negative action is clearly wrong and not semantically difficult, but the model still predicted `Yes`.

Examples:

```text
Task asks to open Chrome, but candidate clicks the system navigation bar.
Task asks to add to cart, but candidate clicks an unrelated blank or browser area.
Candidate clicks a clearly irrelevant control.
```

These are true model mistakes.

Recommended treatment:

```text
keep as clean negative
use to test basic grounding and exact-location sensitivity
```

### 4.4 `semantic_hard_model_error`

The negative action is truly wrong, but visually or semantically related to the task.

Examples:

```text
Task asks to click Add to Cart, but candidate clicks price, stock, or delivery text.
Task asks to choose Canada, but candidate clicks U.S.-related text.
Task asks to open the correct product, but candidate clicks a related but wrong item.
Task requires typing, but candidate clicks a related search suggestion.
```

These are the most valuable hard negatives because they resemble plausible agent mistakes.

Recommended treatment:

```text
keep as hard negative
give higher training weight in later scorer versions
use as a key evaluation subset
```

## 5. Manual Review Counts

The reviewed V2 false positives can be summarized as:

| Main category | Count | Share |
| --- | ---: | ---: |
| `negative_construction_error` | 22 | 42.3% |
| `ambiguous_or_uncertain` | 13 | 25.0% |
| `semantic_hard_model_error` | 11 | 21.2% |
| `clean_model_error` | 6 | 11.5% |
| Total | 52 | 100.0% |

The key observation is that only:

```text
17 / 52
```

are clear model errors worth keeping as strong negatives:

```text
semantic_hard_model_error + clean_model_error
```

The remaining:

```text
35 / 52
```

are mainly negative construction errors or offline-ambiguous cases.

## 6. Main Finding

V2 did not improve overall scorer accuracy, but it revealed the central data problem:

```text
Many GUI action negatives are not valid strong negatives when constructed only from coordinate shifts or different UI bboxes.
```

In mobile GUI tasks, different points may belong to the same functional region:

```text
product card
search suggestion row
search result card
button region
captcha region
permission dialog
```

Therefore, a candidate action can differ from the original ground-truth point but still be a valid or plausible action.

## 7. Implications for V3

V3 should not simply add more data or train longer. It should improve the definition of negative samples.

Recommended V3 changes:

```text
1. Filter negative_construction_error cases.
2. Filter or defer ambiguous_or_uncertain cases.
3. Keep clean_model_error as clean negatives.
4. Keep semantic_hard_model_error as high-value hard negatives.
5. Add candidate visual markers: red dot for click, red arrow for swipe.
6. Treat swipe separately; do not rely on single-screenshot Yes/No labels.
7. Move from bbox-level checks to functional-region-aware checks.
```

For training images:

```text
Draw only the candidate action.
Do not draw the ground-truth action, because that leaks the answer.
```

For analysis pages:

```text
It is fine to draw both candidate and ground-truth markers.
```

## 8. V3 Negative Construction Design

The key change for V3 is to stop treating the raw annotation bbox as the true clickable region.

AITW-style UI annotations often describe visible text, icons, or local OCR boxes. In real GUI interaction, the executable hitbox can be much larger:

```text
search/input text bbox -> whole search bar
button text bbox -> whole button background
product title bbox -> whole product card
search suggestion text bbox -> whole suggestion row
```

Therefore, V3 should introduce:

```text
effective_click_region / functional_region
```

This region is an estimated area where clicks are likely to trigger the same GUI function as the ground-truth action.

### 8.1 Effective Region Rules

Different GUI components need different expansion rules.

| Component | Raw bbox problem | V3 rule |
| --- | --- | --- |
| Search/input bar | bbox may only cover placeholder or typed text | expand strongly in the horizontal direction |
| Button | bbox may only cover text, not button background | expand around the text bbox |
| Product card | image/title/price are separate bboxes but may open the same product | merge into a card-level region |
| Search suggestion | one row may be clickable, not only the text bbox | merge text/icon/arrow into row-level region |
| Swipe/scroll | one screenshot cannot determine correctness reliably | do not use click-style coordinate negatives |

The filtering logic should be conservative:

```text
if candidate is inside the target effective_click_region:
    label as negative_construction_error
    do not train as No

if candidate is inside the same functional region:
    label as ambiguous_or_uncertain
    do not train as strong No

if candidate is outside the target region but semantically related and clearly wrong:
    keep as semantic_hard_model_error / semantic_hard_negative

if candidate is clearly unrelated:
    keep as clean_model_error / clean_negative
```

### 8.2 Handling Shifted Coordinate Negatives

Most observed label noise came from horizontal shifts. This means `shifted_coordinate` should not directly produce a strong `No` label.

The new rule should be:

```text
1. Build the target effective_click_region for the ground-truth action.
2. Generate a shifted candidate.
3. If the candidate remains inside the target region, discard it.
4. If it remains in the same product card, search bar, button, or suggestion row, discard or mark ambiguous.
5. If it lands on a nearby but wrong UI element, keep it as a hard negative.
6. If it lands in a clearly irrelevant non-UI area, keep it as a clean negative.
```

This means V3 should replace one coarse type:

```text
shifted_coordinate
```

with more meaningful outcomes:

```text
negative_construction_error
ambiguous_or_uncertain
near_miss_clean_negative
semantic_hard_negative
```

### 8.3 Recommended Training Set Composition

For strong supervised scorer training, V3 should keep only high-confidence negatives:

```text
clean_negative
semantic_hard_negative
wrong_action_type
```

and filter:

```text
negative_construction_error
ambiguous_or_uncertain
same_functional_region
swipe_uncertain
```

A reasonable starting ratio is:

| Negative group | Suggested share |
| --- | ---: |
| semantic hard negatives | 50% |
| clean negatives | 30% |
| wrong action type negatives | 20% |

The exact ratio can be adjusted after inspecting the resulting badcases. The important principle is:

```text
fewer clean negatives are better than many noisy negatives
```

### 8.4 Project-Level Interpretation

This is a core project finding:

```text
GUI action negative construction cannot rely only on raw UI annotation bboxes.
OCR and accessibility annotations often cover local visual elements, while the true clickable hitbox may be a larger functional region.
Coordinate-shift negatives can therefore create substantial label noise.
```

The practical contribution is to add a functional-region-aware filtering layer before scorer training.

### 8.5 Visualization Example: Checkout Button

The first sample in:

```text
reports/ui_annotation_regions/raw_vs_processed_regions.html
```

is a useful example of why raw UI bboxes are insufficient.

In this Target cart page, the original annotation gives separate small text boxes around:

```text
Sign
in to check out
```

The raw boxes only cover the OCR text. However, the real clickable control is the full red button background. A horizontally shifted click can easily leave the text bbox while still remaining inside the same button. If such a shifted point is labeled as `No`, it becomes label noise.

The processed region therefore estimates a larger:

```text
full_width_cta_button
```

which covers the whole red checkout button. This is closer to the real GUI hitbox and prevents us from constructing false negatives inside the same button.

This example supports the main V3 principle:

```text
raw text bbox -> functional button region
```

instead of:

```text
raw text bbox -> exact clickable boundary
```

### 8.6 Remaining Improvements

The current effective-region rules are still heuristic and should be treated as a diagnostic baseline, not final ground truth.

Important remaining issues:

```text
1. Full-width CTA buttons can be over-expanded if the page contains multiple horizontal controls nearby.
2. Compact controls such as Best Match / Filter need to merge text, icon, and visual button border more reliably.
3. Product card merging is still risky; image, title, price, shipping, and seller text may belong to one card, but the rule can easily merge too much.
4. Search suggestion rows are easier than product cards, but row-level grouping can still confuse adjacent suggestions.
5. Swipe actions cannot be fixed by bbox expansion alone; they need direction, history, and possibly next-state information.
6. The effective region should be used mainly for filtering noisy negatives, not for automatically relabeling samples as positive.
```

The next practical step is to use the visualization report to manually inspect several UI categories and tune the rules separately:

```text
search/input
full-width CTA button
compact control button
search suggestion row
product card
system/navigation controls
```

The region rules should be interpreted by confidence level rather than as a single hard truth:

| Region type | Confidence | Recommended use |
| --- | --- | --- |
| full-width CTA button | high | automatic high-confidence label-noise filtering |
| search/input bar | high / medium | filter only obvious same-input clicks; otherwise ambiguous |
| compact button | medium | usually mark nearby cases as ambiguous |
| search suggestion row | medium / low | ambiguous, not automatic positive or negative |
| product card | low | ambiguous unless the instruction clearly makes it a hard negative |
| browser address bar + website header | low | do not automatically merge; high risk of over-merging |
| navigation/header controls | low | keep or mark semantic hard negative depending on task |
| swipe/scroll region | low | do not use bbox to decide correctness |

The stable positioning is therefore:

```text
effective regions are a high-confidence label-noise filter and ambiguous-sample detector,
not an automatic ground-truth system for action correctness.
```

### 8.7 V3 Filter Dry-Run

Before training a new scorer, we ran a dry-run on the 1k V2 preference pairs:

```text
data/preferences/aitw_single/unseen_subject_train_1000_v2_negatives_check_pairs.jsonl
```

The dry-run does not modify the dataset. It only classifies each rejected action into:

```text
keep
ambiguous
filter
```

using the current effective-region rules.

Output files:

```text
reports/v3_negative_filter_dry_run/v3_negative_filter_summary.json
reports/v3_negative_filter_dry_run/v3_negative_filter_decisions.jsonl
reports/v3_negative_filter_dry_run/v3_negative_filter_samples.html
reports/v3_negative_filter_dry_run/v3_recovered_positive_candidates.html
reports/v3_negative_filter_dry_run/v3_recovered_positive_candidates.jsonl
```

Overall result:

| Decision | Count | Meaning |
| --- | ---: | --- |
| keep | 2319 | usable as strong negative or wrong-action negative |
| ambiguous | 1673 | defer because the current offline rule cannot judge reliably |
| filter | 8 | high-confidence negative construction error / label noise |
| total | 4000 | all V2 preference pairs |

Major categories:

| Category | Count |
| --- | ---: |
| clean_negative | 907 |
| semantic_hard_negative | 459 |
| wrong_action_type | 953 |
| ambiguous_or_uncertain | 1673 |
| negative_construction_error | 8 |

The filtered samples mainly come from:

| Negative type | Filtered count |
| --- | ---: |
| shifted_coordinate | 8 |
| same_screen_element | 0 |
| random_coordinate | 0 |
| wrong_action_type | 0 |

This matches the badcase analysis: coordinate-based negatives are the main source of label noise.

After inspecting over-merged search/header and product-card examples, the filter was made intentionally conservative. The current filter only removes high-confidence cases, mainly full-width CTA button cases where the old shifted coordinate still falls inside the same button region.

Low-confidence region matches are no longer automatically filtered. They are marked as ambiguous instead:

```text
candidate_inside_low_confidence_target_region: 35
candidate_same_low_confidence_functional_region: 1
```

Most ambiguous samples come from non-click ground-truth actions, swipe/scroll cases, and low-confidence effective-region matches:

```text
non_click_gt_unchecked: 1449
swipe_or_scroll_uncertain: 188
```

This is expected because effective-region rules currently only provide reliable evidence for click-like actions. For type, finish, wait, and swipe actions, we should defer judgment unless we have additional context or next-state information.

The dry-run supports the V3 direction:

```text
1. Use effective regions to remove obvious label noise.
2. Do not force uncertain non-click or swipe cases into strong Yes/No labels.
3. Keep clean negatives, semantic hard negatives, and wrong-action-type negatives.
4. Inspect filtered examples manually before using the rules for actual V3 dataset construction.
```

The most important inspection file is:

```text
reports/v3_negative_filter_dry_run/v3_recovered_positive_candidates.html
```

It only contains the 8 old negative samples that the conservative high-confidence effective-region rule would remove from strong negative training. These are not automatically relabeled as positive, but they are treated as:

```text
not_strong_negative / likely_label_noise
```

This is the cleanest way to validate whether the V3 region rules are improving negative-sample quality.

### 8.8 Proposed V3 Ablations

Only filtering the 8 high-confidence label-noise samples is safe, but it may be too small to visibly change scorer training. Therefore, V3 should be evaluated with at least two data variants:

```text
v3-clean-filter
```

This version removes only high-confidence label-noise samples:

```text
filter: 8
```

It is the safest version and demonstrates that the filtering rule does not aggressively delete hard negatives.

```text
v3-ambiguous-removed
```

This version removes both:

```text
high-confidence filter samples
ambiguous_or_uncertain samples
```

It is more likely to affect training because it removes uncertain negatives from strong supervision.

The comparison should include:

```text
v2
v3-clean-filter
v3-ambiguous-removed
```

Evaluation should focus less on overall accuracy and more on:

```text
No->Yes false positives
wrong_ui_element false positives
near_miss false positives
swipe false positives
hard negative accuracy
whether Yes accuracy drops too much
```

If `v3-ambiguous-removed` reduces false positives while preserving acceptable Yes accuracy, then the bbox/effective-region work has direct value for scorer training.

As a later refinement, ambiguous samples can also be down-weighted instead of removed:

```text
clean_negative: 1.0
semantic_hard_negative: 1.5
ambiguous_uncertain: 0.2 or excluded
label_noise: removed
```

The first implementation can remain simple:

```text
label_noise removed
ambiguous excluded from strong supervision
clean_negative / semantic_hard_negative / wrong_action_type retained
```

### 8.9 Manual Precision Check

The dry-run should not be judged only by counts. A small manual precision check would make the bbox work more convincing.

Suggested review:

```text
filter samples: inspect all 8, or 50 if more are produced later
ambiguous samples: sample 50
keep samples: sample 50
```

Manual labels:

```text
filter precision = how many filtered samples are truly label noise
ambiguous precision = how many ambiguous samples are truly unsafe as strong No
keep precision = how many kept samples are truly clean or hard negatives
```

This connects the bbox work to dataset quality, not just to heuristic region counts.

## 9. Updated Project Conclusion

The current experiments show that the project is valuable not because V2 already beats V1, but because the V1/V2 comparison exposes a core issue in GUI action scorer data construction:

```text
Naive negative sampling can create many false negatives.
These noisy negatives make the scorer learn page relevance rather than exact action correctness.
```

The next stage should focus on:

```text
functional-region-aware negative filtering
ambiguous action filtering
candidate-marker scorer inputs
semantic hard negative mining
```

This keeps the project scoped as a practical offline scorer data system, while leaving full online PRM or agent execution for a later stage.
