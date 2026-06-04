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

## 8. Updated Project Conclusion

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
