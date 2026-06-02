# Mobile GUI Agent Data-Centric Post-training

面向移动端视觉 GUI Agent 的数据清洗、动作奖励设计与偏好数据构造工程。

这个项目的重点不是复刻一个完整 GUI Agent SFT/RL 闭环，而是构建一套可验证的数据与 reward 系统：

```text
GUI trajectory data
-> step-level sample parsing
-> data audit and quality scoring
-> step-level action reward
-> chosen/rejected preference construction
-> rule reward reranking / optional action scorer
-> offline and small-scale online evaluation
```

## Project Layout

```text
configs/                         # 默认配置与实验配置
data/
  raw/                           # AITW / AndroidControl 原始数据占位
  interim/                       # step-level 中间结果
  processed/                     # 清洗后数据
  preferences/                   # chosen/rejected preference pairs
experiments/                     # 消融实验配置与记录
notebooks/                       # 探索性分析
reports/                         # 实验报告、错误分析、图表
scripts/                         # 命令行脚本入口
src/mobile_gui_agent_data/
  schemas/                       # action / step / preference 数据结构
  datasets/                      # AITW、AndroidControl 解析适配
  audit/                         # 数据清洗规则与 quality score
  rewards/                       # format/type/coordinate/text/state reward
  preference/                    # 负样本采样与 preference pair 构造
  reranking/                     # rule reward reranking baseline
  evaluation/                    # Top-k、MRR、pairwise accuracy 等指标
  utils/                         # IO、图像差异等工具
tests/                           # 单元测试
```

## Core Modules

1. `schemas`: 统一 GUI action schema，支持 `click/type/scroll/back/home/wait/finish`。
2. `datasets`: 将 episode 拆分为 screenshot-instruction-action step-level 样本。
3. `audit`: 实现坐标越界、非法动作、重复动作、异常文本、无状态变化等清洗规则。
4. `rewards`: 实现 step-level action reward，并组合为 hybrid reward。
5. `preference`: 基于真实动作构造 chosen/rejected preference pairs，支持 random、structured、hard negative 扩展。
6. `reranking`: 对多个 candidate actions 用 rule reward 重新排序，验证 reward 是否能提升动作选择。
7. `evaluation`: 计算 pairwise accuracy、Top-1、Top-3、MRR、invalid action rate 等指标。

## First Milestones

```text
Week 1: step-level parser + action schema + data statistics
Week 2-3: audit pipeline + quality score + data split
Week 4-5: reward library + reward ablation
Week 6-7: preference builder + negative sampling ablation
Week 8-9: rule reranking baseline + optional action scorer
Week 10-11: AndroidWorld small-scale validation
Week 12: report, figures, README, resume bullets
```

## Quick Start

```bash
pip install -r requirements.txt
python scripts/download_aitw_single_sample.py --subset unseen_subject --split train --limit 100 --output data/raw/aitw_single/unseen_subject_train_100.jsonl --image-dir data/raw/aitw_single/images
python scripts/prepare_aitw_single_sample.py --subset unseen_subject --split train --limit 1000 --qdd-samples 200
python scripts/reprocess_aitw_single_raw.py --raw data/raw/aitw_single/unseen_subject_train_1000_with_images.jsonl --qdd-samples 200
python scripts/inspect_raw_records.py --input examples/demo_episodes.jsonl --output reports/demo_raw_schema.json
python scripts/parse_episodes.py --source aitw --input examples/demo_episodes.jsonl --output data/interim/demo_steps.jsonl
python scripts/normalize_steps.py --input data/interim/demo_steps.jsonl --output data/interim/demo_steps_norm1000.jsonl
python scripts/summarize_steps.py --input data/interim/demo_steps_norm1000.jsonl --output reports/demo_step_summary.json
python scripts/run_audit.py --input data/interim/steps.jsonl --output data/processed/audited_steps.jsonl
python scripts/select_qdd_samples.py --input data/processed/audited_steps.jsonl --output data/processed/qdd_selected_steps.jsonl --max-samples 200
python scripts/build_preferences.py --input data/processed/audited_steps.jsonl --output data/preferences/pairs.jsonl
python scripts/build_scorer_dataset.py --input data/preferences/pairs.jsonl --output data/scorer/scorer_yesno.jsonl
python scripts/evaluate_rule_reward_on_pairs.py --input data/preferences/pairs.jsonl --output reports/rule_reward_baseline.json
```

当前框架先提供离线数据与规则 reward 的最小闭环，后续可以继续接入 Qwen2.5-VL LoRA action scorer 和 AndroidWorld 验证。

Preference negatives currently include random coordinates, same-screen UI
elements, shifted coordinates, and wrong action types. Same-screen negatives use
AITW UI annotations to reduce false negatives caused by shifting within the same
large clickable region.
