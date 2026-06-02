# Server Training Setup

This project should be uploaded to GitHub without generated data, screenshots,
checkpoints, or reports. The server can regenerate AITW samples from Hugging
Face.

## 1. Clone

```bash
git clone <your-repo-url>
cd <repo>
```

## 2. Create Environment

```bash
conda env create -f environment.yml
conda activate mobile-gui-agent-data
python -m pip install -e .
```

If the server already has a CUDA/PyTorch stack managed by the admin, create the
environment first, then install the matching PyTorch build following the server
CUDA version.

For AutoDL images with a preinstalled CUDA PyTorch, avoid reinstalling `torch`
from the general `requirements.txt`. Use:

```bash
pip install -r requirements-server.txt
pip install -e .
```

If `transformers` disables PyTorch or NumPy reports ABI errors, repair the
environment with:

```bash
pip install "numpy==1.26.4"
pip install "transformers>=4.49,<5" "accelerate>=0.30" "peft>=0.11" qwen-vl-utils
```

## 3. Verify GPU Environment

```bash
python scripts/verify_training_environment.py
```

Expected for A800:

```text
cuda.available = true
device_count >= 1
device name contains A800
```

## 4. Prepare AITW Single Data

Small smoke test:

```bash
PYTHONPATH=src python scripts/prepare_aitw_single_sample.py \
  --subset unseen_subject \
  --split train \
  --limit 1000 \
  --qdd-samples 200
```

This regenerates:

```text
data/raw/aitw_single/
data/interim/aitw_single/
data/processed/aitw_single/
data/preferences/aitw_single/
data/scorer/aitw_single/
reports/aitw_single/
```

These paths are ignored by Git.

## 5. Build Scorer Data

```bash
PYTHONPATH=src python scripts/build_scorer_dataset.py \
  --input data/preferences/aitw_single/unseen_subject_train_1000_pairs.jsonl \
  --output data/scorer/aitw_single/unseen_subject_train_1000_scorer_yesno.jsonl
```

Split by instruction before training:

```bash
PYTHONPATH=src python scripts/split_scorer_dataset.py \
  --input data/scorer/aitw_single/unseen_subject_train_1000_scorer_yesno.jsonl \
  --output-dir data/scorer/aitw_single/unseen_subject_train_1000_splits

PYTHONPATH=src python scripts/summarize_scorer_dataset.py \
  --input data/scorer/aitw_single/unseen_subject_train_1000_splits/train.jsonl \
  --output reports/aitw_single/scorer_train_summary.json \
  --image-root .
```

## 6. Rule Reward Baseline

```bash
PYTHONPATH=src python scripts/evaluate_rule_reward_on_pairs.py \
  --input data/preferences/aitw_single/unseen_subject_train_1000_pairs.jsonl \
  --output reports/aitw_single/unseen_subject_train_1000_rule_reward_baseline.json
```

## 7. Next Training Target

The planned first model experiment is a Qwen2.5-VL-3B LoRA Yes/No action scorer:

```text
image + instruction + candidate_action -> Yes / No
```

The starting config is:

```text
configs/scorer_qwen2_5_vl_lora.yaml
```

Before full training, create instruction-wise train/val/test splits for the
scorer JSONL and run a 100-sample overfit test.

Smoke test:

```bash
PYTHONPATH=src python scripts/train_qwen_vl_scorer.py \
  --config configs/scorer_qwen2_5_vl_lora.yaml \
  --model-name-or-path /root/autodl-tmp/hf_models/Qwen2.5-VL-3B-Instruct \
  --train-path /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_splits/train.jsonl \
  --val-path /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_splits/val.jsonl \
  --image-root /root/autodl-tmp/GUI-PRM \
  --output-dir /root/autodl-tmp/GUI-PRM/outputs/qwen_scorer_smoke \
  --attn-implementation eager \
  --max-train-samples 100 \
  --max-val-samples 64 \
  --max-steps 10
```

Evaluate the smoke adapter:

```bash
PYTHONPATH=src python scripts/evaluate_qwen_vl_scorer.py \
  --config configs/scorer_qwen2_5_vl_lora.yaml \
  --model-name-or-path /root/autodl-tmp/hf_models/Qwen2.5-VL-3B-Instruct \
  --adapter-path /root/autodl-tmp/GUI-PRM/outputs/qwen_scorer_smoke \
  --input /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_splits/val.jsonl \
  --image-root /root/autodl-tmp/GUI-PRM \
  --output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_smoke_val_eval.json \
  --predictions-output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_smoke_val_predictions.jsonl \
  --attn-implementation eager \
  --max-samples 128
```

Inspect false positives after evaluation:

```bash
PYTHONPATH=src python scripts/inspect_scorer_errors.py \
  --input /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_test_predictions.jsonl \
  --summary-output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_test_error_summary.json \
  --errors-output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_test_false_positive_errors.jsonl \
  --html-output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_test_false_positive_errors.html \
  --image-root /root/autodl-tmp/GUI-PRM \
  --pairs /root/autodl-tmp/GUI-PRM/data/preferences/aitw_single/unseen_subject_train_1000_pairs.jsonl \
  --focus "No->Yes" \
  --limit 80
```

Full first pass:

```bash
PYTHONPATH=src python scripts/train_qwen_vl_scorer.py \
  --config configs/scorer_qwen2_5_vl_lora.yaml \
  --train-path /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_splits/train.jsonl \
  --val-path /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_splits/val.jsonl \
  --image-root /root/autodl-tmp/GUI-PRM \
  --output-dir /root/autodl-tmp/GUI-PRM/outputs/qwen2_5_vl_3b_action_scorer_lora
```

## 8. V2 Negative Data Experiment

Regenerate the same 1000-step sample with the current action-aware negative
samplers:

```bash
PYTHONPATH=src python scripts/reprocess_aitw_single_raw.py \
  --raw /root/autodl-tmp/GUI-PRM/data/raw/aitw_single/unseen_subject_train_1000_with_images.jsonl \
  --tag unseen_subject_train_1000_v2 \
  --qdd-samples 200 \
  --root /root/autodl-tmp/GUI-PRM
```

Summarize the generated preference pairs before training:

```bash
PYTHONPATH=src python scripts/summarize_preference_pairs.py \
  --input /root/autodl-tmp/GUI-PRM/data/preferences/aitw_single/unseen_subject_train_1000_v2_pairs.jsonl \
  --output /root/autodl-tmp/GUI-PRM/reports/aitw_single/unseen_subject_train_1000_v2_pair_summary.json
```

Build and split scorer records:

```bash
PYTHONPATH=src python scripts/build_scorer_dataset.py \
  --input /root/autodl-tmp/GUI-PRM/data/preferences/aitw_single/unseen_subject_train_1000_v2_pairs.jsonl \
  --output /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v2_scorer_yesno.jsonl

PYTHONPATH=src python scripts/split_scorer_dataset.py \
  --input /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v2_scorer_yesno.jsonl \
  --output-dir /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v2_splits
```

Train the v2 scorer:

```bash
PYTHONPATH=src python scripts/train_qwen_vl_scorer.py \
  --config configs/scorer_qwen2_5_vl_lora.yaml \
  --model-name-or-path /root/autodl-tmp/hf_models/Qwen2.5-VL-3B-Instruct \
  --train-path /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v2_splits/train.jsonl \
  --val-path /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v2_splits/val.jsonl \
  --image-root /root/autodl-tmp/GUI-PRM \
  --output-dir /root/autodl-tmp/GUI-PRM/outputs/qwen_scorer_1k_v2 \
  --attn-implementation eager
```

Evaluate v2 on val and test:

```bash
PYTHONPATH=src python scripts/evaluate_qwen_vl_scorer.py \
  --config configs/scorer_qwen2_5_vl_lora.yaml \
  --model-name-or-path /root/autodl-tmp/hf_models/Qwen2.5-VL-3B-Instruct \
  --adapter-path /root/autodl-tmp/GUI-PRM/outputs/qwen_scorer_1k_v2 \
  --input /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v2_splits/val.jsonl \
  --image-root /root/autodl-tmp/GUI-PRM \
  --output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v2_val_eval.json \
  --predictions-output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v2_val_predictions.jsonl \
  --attn-implementation eager

PYTHONPATH=src python scripts/evaluate_qwen_vl_scorer.py \
  --config configs/scorer_qwen2_5_vl_lora.yaml \
  --model-name-or-path /root/autodl-tmp/hf_models/Qwen2.5-VL-3B-Instruct \
  --adapter-path /root/autodl-tmp/GUI-PRM/outputs/qwen_scorer_1k_v2 \
  --input /root/autodl-tmp/GUI-PRM/data/scorer/aitw_single/unseen_subject_train_1000_v2_splits/test.jsonl \
  --image-root /root/autodl-tmp/GUI-PRM \
  --output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v2_test_eval.json \
  --predictions-output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v2_test_predictions.jsonl \
  --attn-implementation eager
```

Inspect v2 false positives and compare v1 vs v2:

```bash
PYTHONPATH=src python scripts/inspect_scorer_errors.py \
  --input /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v2_test_predictions.jsonl \
  --summary-output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v2_test_error_summary.json \
  --errors-output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v2_test_false_positive_errors.jsonl \
  --html-output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v2_test_false_positive_errors.html \
  --image-root /root/autodl-tmp/GUI-PRM \
  --pairs /root/autodl-tmp/GUI-PRM/data/preferences/aitw_single/unseen_subject_train_1000_v2_pairs.jsonl \
  --focus "No->Yes" \
  --limit 80

PYTHONPATH=src python scripts/compare_scorer_runs.py \
  --eval v1=/root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_test_eval.json \
  --eval v2=/root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v2_test_eval.json \
  --error-summary v1=/root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_test_error_summary.json \
  --error-summary v2=/root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v2_test_error_summary.json \
  --output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v1_vs_v2_comparison.json \
  --markdown-output /root/autodl-tmp/GUI-PRM/reports/aitw_single/qwen_scorer_1k_v1_vs_v2_comparison.md
```
