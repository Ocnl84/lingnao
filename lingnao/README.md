# PRJ-01 灵脑 — 工业指令微调 Demo

WAM（世界动作模型）架构第一层：将工人自然语言指令转为结构化 JSON，交给下游灵境（世界模型）做安全预演。

## 快速开始

```bash
# Mock 模式（无需 GPU，演示完整流程）
python run_demo.py --mock

# 交互模式（输入指令看输出）
python run_demo.py --interactive

# 有 GPU 时跑完整流程
python run_demo.py
```

## 项目结构

```
demo/
├── run_demo.py                  # 主入口
└── lingnao/
    ├── __init__.py              # 包说明
    ├── config.py                # 统一配置（路径/超参/提示词）
    ├── data_generator.py        # 训练数据生成器（8 种任务类型）
    ├── evaluator.py             # 评测模块（字段级严格匹配）
    ├── trainer.py               # QLoRA 微调脚本（技术方案第八节）
    ├── inference.py             # 推理脚本（加载 LoRA 推理）
    ├── data/                    # 数据集目录
    │   ├── train_v1.jsonl       # 训练集
    │   └── test_v1.jsonl        # 测试集
    └── outputs/                 # 输出目录
        ├── lora_out/            # LoRA 适配器
        ├── preds.jsonl          # 预测结果
        └── demo_report.json     # Demo 报告
```

## Demo 流程

| 步骤 | 内容 | 说明 |
|:---|:---|:---|
| Step 1 | 数据生成 | 8 种任务类型，生成训练/测试集 |
| Step 2 | 基线测试 | 微调前评估基座模型指令理解能力 |
| Step 3 | QLoRA 微调 | 4bit 量化微调，显存 ~15-18G |
| Step 4 | 推理评测 | 加载 LoRA 适配器，跑测试集 |
| Step 5 | 对比报告 | 基线 vs 微调后，评估 88% 达标 |

## 8 种任务类型

| 编号 | task_type | 典型话术 |
|:---|:---|:---|
| 1 | 取料_放置 | "把那个蓝色的螺丝放到左边第二个盒子里" |
| 2 | 装配 | "把螺母拧到螺丝上" |
| 3 | 换线 | "切到 3 号产线" |
| 4 | 质检 | "看下这个零件有没有划痕" |
| 5 | 搬运 | "把这箱零件搬到 A 区传送带" |
| 6 | 异常应对 | "零件要掉了！接住" |
| 7 | 状态查询 | "现在做到第几个了" |
| 8 | 协作等待 | "等一下，我还没走开" |

## 技术栈

- **基座模型**: Qwen3-VL-8B-Instruct（阿里 2025-12）
- **微调方法**: QLoRA 4bit（NF4 量化 + LoRA r=16）
- **可训参数**: ~18M / 8B (0.23%)
- **显存占用**: ~15-18G（QLoRA）vs 130G+（全量微调）
- **LoRA 体积**: ~70MB（vs 16G 全模型）

## 评测方法

严格 JSON 字段级匹配（不依赖 LLM-as-Judge）：
- **must_match 字段**: 必须完全匹配，错了扣全分
- **optional 字段**: 对了加分，错了不扣
- **达标线**: 100 条测试集平均分 ≥ 0.88

## 模块说明

### data_generator.py
按技术方案第四节格式生成训练数据。每条样本包含 `worker_utterance`（工人原话）、`world_state`（场景对象）、`expected_output`（结构化 JSON 答案）、`eval_criteria`（评测规则）。

### evaluator.py
实现技术方案第七节的字段级严格匹配评测。支持 4 级 JSON 解析容错：直接 parse → 正则找 ```json``` 块 → 找 `{...}` 区间 → 失败返回 None。

### trainer.py
技术方案第八节的完整 QLoRA 训练脚本。包含 ChatML 渲染、assistant 段 loss mask、4bit 量化、LoRA 配置。输出 ~70MB 的 LoRA 适配器。

### inference.py
技术方案第九节的推理脚本。支持动态加载 LoRA（不合并权重）、批量推理、交互模式。

## 环境要求

- **GPU 模式**: RTX 5090 (32G) / A100 (40G+), CUDA 12.x
- **依赖**: transformers, peft, bitsandbytes, datasets, torch, accelerate
- **Mock 模式**: 仅需 Python 3.10+
