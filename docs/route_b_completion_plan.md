# Route B Completion Plan

## Goal

收敛后的项目目标不再是完整在线 PRM，而是：

```text
验证负样本质量控制是否能降低 GUI action scorer 的 No->Yes false positive。
```

核心问题：

```text
减少 noisy / ambiguous negatives 后，scorer 是否更少把错误动作判断为 Yes？
```

## Current Data Variants

基于 V2 preference pairs 和 V3 dry-run decision，我们已经生成两个 V3 消融数据集。

### v3-clean-filter

只删除高置信 label noise：

```text
drop: filter
```

数据规模：

```text
pairs: 3992
scorer records: 7984
train: 6164
val: 806
test: 1014
```

文件：

```text
data/preferences/aitw_single/unseen_subject_train_1000_v3_clean_filter_pairs.jsonl
data/scorer/aitw_single/unseen_subject_train_1000_v3_clean_filter_scorer_yesno.jsonl
data/scorer/aitw_single/unseen_subject_train_1000_v3_clean_filter_splits/
reports/aitw_single/unseen_subject_train_1000_v3_clean_filter_summary.json
```

### v3-ambiguous-removed

删除高置信 label noise 和 ambiguous 样本：

```text
drop: filter + ambiguous
```

数据规模：

```text
pairs: 2319
scorer records: 4638
train: 3624
val: 462
test: 552
```

文件：

```text
data/preferences/aitw_single/unseen_subject_train_1000_v3_ambiguous_removed_pairs.jsonl
data/scorer/aitw_single/unseen_subject_train_1000_v3_ambiguous_removed_scorer_yesno.jsonl
data/scorer/aitw_single/unseen_subject_train_1000_v3_ambiguous_removed_splits/
reports/aitw_single/unseen_subject_train_1000_v3_ambiguous_removed_summary.json
```

## Rebuild Command

如果服务器没有这些文件，可以先重新生成：

```bash
cd /root/GUI-PRM
export PYTHONPATH=src

python scripts/dry_run_v3_negative_filter.py \
  --input /root/autodl-tmp/GUI-PRM/data/preferences/aitw_single/unseen_subject_train_1000_v2_negatives_check_pairs.jsonl \
  --output-dir /root/autodl-tmp/GUI-PRM/reports/v3_negative_filter_dry_run \
  --image-root /root/autodl-tmp/GUI-PRM

python scripts/build_v3_scorer_ablation_datasets.py \
  --pairs /root/autodl-tmp/GUI-PRM/data/preferences/aitw_single/unseen_subject_train_1000_v2_negatives_check_pairs.jsonl \
  --decisions /root/autodl-tmp/GUI-PRM/reports/v3_negative_filter_dry_run/v3_negative_filter_decisions.jsonl \
  --prefix unseen_subject_train_1000_v3 \
  --preference-dir /root/autodl-tmp/GUI-PRM/data/preferences/aitw_single \
  --scorer-dir /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single \
  --report-dir /root/autodl-tmp/GUI-PRM/reports/aitw_single
```

## Training Commands

### Train v3-clean-filter

```bash
cd /root/GUI-PRM
export OMP_NUM_THREADS=1
export HF_HOME=/root/autodl-tmp/hf_cache
export PYTHONPATH=src

python scripts/train_qwen_vl_scorer.py \
  --config configs/scorer_qwen2_5_vl_lora.yaml \
  --model-name-or-path /root/autodl-tmp/hf_models/Qwen2.5-VL-3B-Instruct \
  --train-path /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v3_clean_filter_splits/train.jsonl \
  --val-path /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v3_clean_filter_splits/val.jsonl \
  --image-root /root/autodl-tmp/GUI-PRM \
  --output-dir /root/autodl-tmp/GUI-PRM/outputs/qwen_scorer_1k_v3_clean_filter \
  --attn-implementation eager
```

### Train v3-ambiguous-removed

```bash
cd /root/GUI-PRM
export OMP_NUM_THREADS=1
export HF_HOME=/root/autodl-tmp/hf_cache
export PYTHONPATH=src

python scripts/train_qwen_vl_scorer.py \
  --config configs/scorer_qwen2_5_vl_lora.yaml \
  --model-name-or-path /root/autodl-tmp/hf_models/Qwen2.5-VL-3B-Instruct \
  --train-path /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v3_ambiguous_removed_splits/train.jsonl \
  --val-path /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v3_ambiguous_removed_splits/val.jsonl \
  --image-root /root/autodl-tmp/GUI-PRM \
  --output-dir /root/autodl-tmp/GUI-PRM/outputs/qwen_scorer_1k_v3_ambiguous_removed \
  --attn-implementation eager
```

## Evaluation Commands

### Evaluate v3-clean-filter

```bash
python scripts/evaluate_qwen_vl_scorer.py \
  --config configs/scorer_qwen2_5_vl_lora.yaml \
  --input /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v3_clean_filter_splits/test.jsonl \
  --image-root /root/autodl-tmp/GUI-PRM \
  --model-name-or-path /root/autodl-tmp/hf_models/Qwen2.5-VL-3B-Instruct \
  --adapter-path /root/autodl-tmp/GUI-PRM/outputs/qwen_scorer_1k_v3_clean_filter \
  --output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v3_clean_filter_test_eval.json \
  --predictions-output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v3_clean_filter_test_predictions.jsonl \
  --attn-implementation eager
```

### Evaluate v3-ambiguous-removed

```bash
python scripts/evaluate_qwen_vl_scorer.py \
  --config configs/scorer_qwen2_5_vl_lora.yaml \
  --input /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v3_ambiguous_removed_splits/test.jsonl \
  --image-root /root/autodl-tmp/GUI-PRM \
  --model-name-or-path /root/autodl-tmp/hf_models/Qwen2.5-VL-3B-Instruct \
  --adapter-path /root/autodl-tmp/GUI-PRM/outputs/qwen_scorer_1k_v3_ambiguous_removed \
  --output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v3_ambiguous_removed_test_eval.json \
  --predictions-output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v3_ambiguous_removed_test_predictions.jsonl \
  --attn-implementation eager
```

## What To Compare

主要对比：

```text
v2
v3-clean-filter
v3-ambiguous-removed
```

重点指标：

```text
No->Yes false positives
No accuracy
Yes accuracy
shifted_coordinate accuracy
same_screen_element / wrong_ui_element accuracy
wrong_action_type accuracy
swipe accuracy
```

不要只看 overall accuracy。路线 B 的核心结论是数据质量，因此最重要的是：

```text
No->Yes 是否减少
错误动作是否更少被放过
Yes accuracy 是否没有严重下降
```

## Finish Criteria

项目可以在以下条件满足后收尾：

```text
1. v1/v2/v3 的训练和测试结果齐全。
2. badcase 和 bbox 分析报告完成。
3. v3-clean-filter / v3-ambiguous-removed 至少完成一个训练评估。
4. 能说明负样本质量控制对 false positives 的影响。
5. 结论收束为 GUI action scorer 数据质量研究，而不是完整在线 PRM。
```
