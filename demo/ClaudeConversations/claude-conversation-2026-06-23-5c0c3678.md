# Claude Conversation Log

Session ID: 5c0c3678-65d5-49c8-bcfc-8a4d9cc5014e
Date: 2026-06-23 07:33:27

---

## 👤 User

把eval相关的代码整理到一个文件夹里吧，并把可能出问题的引入修改一下

---

## 🤖 Claude

Now let me read all the eval files to understand their internal imports before moving them.

---

## 🤖 Claude

Now let me read the files that import from the eval modules:

---

## 🤖 Claude

Now I have a full picture. Let me execute the reorganization step by step.

---

## 👤 User

[Request interrupted by user for tool use]

---

## 👤 User

解释一下在git什么

---

## 🤖 Claude

目前 git 的状态：

**已暂存（staged）6 个文件重命名** — `git mv` 会自动 stage，git 识别为 `renamed` 而非删除+新增：

| 原路径 | → 新路径 |
|--------|----------|
| `demo/lingnao/eval_config.yaml` | `demo/lingnao/eval/config.yaml` |
| `demo/lingnao/eval_matchers.py` | `demo/lingnao/eval/matchers.py` |
| `demo/lingnao/eval_metrics.py` | `demo/lingnao/eval/metrics.py` |
| `demo/lingnao/eval_model_graded.py` | `demo/lingnao/eval/model_graded.py` |
| `demo/test_evaluator.py` | `demo/lingnao/eval/tests.py` |
| `demo/lingnao/eval_types.py` | `demo/lingnao/eval/types.py` |

**还没处理的是 `evaluator.py`** — 它需要变成 `eval/__init__.py`，但 `git mv` 没办法直接把一个普通文件重命名为 `__init__.py`（它不是目录，`__init__.py` 需要放在 `eval/` 目录下）。刚才我用了 `cp` + `git rm`，但你中断了。

更好的做法是先把 `evaluator.py` 的内容编辑好后再写入 `eval/__init__.py`，然后用 `git rm` 删掉旧的。要我现在继续吗？

---

## 👤 User

继续

---

## 🤖 Claude

好，7 个文件全部移动完成。现在逐一修复内部导入。

---

## 🤖 Claude

Now let me fix all files. Starting with the internal imports in the eval package:

---

## 🤖 Claude

Now convert the CLI block into a `main()` function:

---

## 🤖 Claude

Now create `__main__.py` and fix the remaining files in parallel:

---

## 🤖 Claude

Now fix the other files. First, read the ones that need editing:

---

## 🤖 Claude

Now fix the placeholder error message in matchers.py and model_graded.py:

---

## 🤖 Claude

Now fix the external consumers — the files outside eval that import from it:

---

## 🤖 Claude

All source edits done. Let me verify the structure and run tests:

---

## 🤖 Claude

All tests pass. Let me also verify the external imports work:

---

## 🤖 Claude

All imports verified. Now update the documentation:

---

## 🤖 Claude

Now update the README:

---

## 🤖 Claude

Clean up old pycache and verify final state:

---

## 🤖 Claude

全部完成。以下是变更总结：

---

## 变更总结

### 新目录结构 `demo/lingnao/eval/`

```
demo/lingnao/eval/
├── __init__.py      # ← 原 evaluator.py（Eval 类 + safe_parse_json + score_sample + CLI）
├── __main__.py      # ← 新增，支持 python -m lingnao.eval --preds ...
├── types.py         # ← 原 eval_types.py
├── matchers.py      # ← 原 eval_matchers.py
├── metrics.py       # ← 原 eval_metrics.py
├── model_graded.py  # ← 原 eval_model_graded.py
├── config.yaml      # ← 原 eval_config.yaml
└── tests.py         # ← 原 demo/test_evaluator.py
```

### 修改的导入点（共 10 处）

| 文件 | 修改 |
|------|------|
| `eval/__init__.py` | `.eval_types` → `.types`, `.eval_matchers` → `.matchers`, `.eval_metrics` → `.metrics`, `.eval_model_graded` → `.model_graded`, `.config` → `..config` |
| `eval/metrics.py` | `.eval_types` → `.types` |
| `eval/matchers.py` | `.eval_types` → `.types` |
| `eval/model_graded.py` | `.eval_types` → `.types`, `.eval_matchers` → `.matchers`, `.inference` → `..inference`, `.config` → `..config` |
| `eval/tests.py` | `from lingnao.evaluator` → `from lingnao.eval` + path 修正 |
| `run_demo.py` | `from lingnao.evaluator` → `from lingnao.eval` |
| `inference.py` | `.evaluator` → `.eval`（relative + fallback 两处） |
| `config.py` | `eval_config.yaml` → `eval/config.yaml` |
| `CLAUDE.md` | 文档路径更新 |
| `README.md` | 文档路径更新 |

### CLI 用法变更

```bash
# 旧: python demo/lingnao/evaluator.py --preds ...
# 新: python -m lingnao.eval --preds ...
```

---

## 👤 User

cli是啥

---

## 🤖 Claude

CLI = Command Line Interface（命令行接口）。

就是可以在终端里直接跑的命令，不 import 模块，而是传参数执行。比如：

```bash
# 评测模块的 CLI —— 直接在命令行跑评测
python -m lingnao.eval --preds outputs/preds.jsonl --test data/test_v2.jsonl --threshold 0.88
```

对应代码在 `eval/__init__.py` 底部那个 `main()` 函数 — 它用 `argparse` 解析 `--preds`、`--test` 这些参数，然后调 Eval 跑评测、打报告。`__main__.py` 让你能用 `python -m lingnao.eval` 的方式触发它。

---

## 👤 User

跑一下demo

---

## 🤖 Claude

Demo 跑通了，评测模块的重构没有问题。结果摘要：

| 指标 | 值 |
|------|-----|
| 基线均分 | **79.2%** |
| JSON 解析率 | **100%** |
| 达标线 | 88% |
| 整体达标 | ❌ 未达标 |

**按任务类型：**

| ✅ 达标 (4/8) | ❌ 未达标 (4/8) |
|--------------|----------------|
| 换线 100% | 协作等待 58.3% |
| 装配 94.0% | 异常应对 52.8% |
| 质检 93.4% | 搬运 67.9% |
| 状态查询 91.7% | 取料放置 72.1% |

主要问题集中在 force 近义词（轻→稍轻/温柔）、object 辨识（螺母→工件）、以及「协作等待」被误判为「异常应对」这几类错误。这些都是基座模型没微调的正常表现。

---

## 👤 User

运行一遍完整的demo包括微调

---

## 🤖 Claude

48G 显存，够用。直接跑完整 demo：

---

## 🤖 Claude

训练任务已在后台运行（ID: `bk4dd8797`），这需要一些时间——3 epoch × 1056 条样本。可以用以下命令查看进度：

```bash
# 查看实时输出
tail -f /tmp/claude-0/-root-Brain/5c0c3678-65d5-49c8-bcfc-8a4d9cc5014e/tasks/bk4dd8797.output

# 或检查任务状态
```

要我等待完成后再展示结果吗？

---

## 👤 User

tail -f /tmp/claude-0/-root-Brain/5c0c3678-65d5-49c8-bcfc-8a4d9cc5014e/tasks/bk4dd8797.output

---

## 🤖 Claude

训练正在进行中：

- ✅ **Step 2 基线测试** — 完成（79.2%）
- 🔄 **Step 3 QLoRA 微调** — 进行中（6/198 it，~8.3s/it，预计还需 ~27 分钟）

等训练完会自动跑 Step 4 微调后评测 + Step 5 对比报告。我稍后再来查看结果。

---

## 👤 User

查看最新输出进度

---

## 🤖 Claude

进度不错：

| 指标 | 值 |
|------|-----|
| 进度 | **77/198** (39%) |
| 耗时 | ~10 分钟 |
| 预计剩余 | ~17 分钟 |
| 当前 loss | **~0.03**（已从 0.30 收敛） |
| 当前 epoch | 第 2 轮 |

loss 已经降到很低了，训练正常收敛中。

---

## 👤 User

<task-notification>
<task-id>bk4dd8797</task-id>
<tool-use-id>call_00_3cXO7n8YxLTFQuBSVw124831</tool-use-id>
<output-file>/tmp/claude-0/-root-Brain/5c0c3678-65d5-49c8-bcfc-8a4d9cc5014e/tasks/bk4dd8797.output</output-file>
<status>completed</status>
<summary>Background command "Run full demo with QLoRA training" completed (exit code 0)</summary>
</task-notification>

---

## 🤖 Claude

训练完成！查看最终结果：

---

## 🤖 Claude

完整 Demo 跑完，结果如下：

## PRJ-01 灵脑 — 完整 Demo 报告

| 指标 | 基线（微调前） | 微调后 | 提升 |
|------|:----------:|:-----:|:----:|
| 均分 | 79.2% | **96.7%** | **+17.4%** |
| JSON 解析率 | 100% | 100% | — |
| 达标 | ❌ | ✅ | — |

### 微调后按任务类型

| ✅ 7/8 达标 | 分数 | ❌ 1/8 未达标 | 分数 |
|------------|:---:|------------|:---:|
| 协作等待 | **100%** | 异常应对 | 80.6% |
| 取料放置 | **100%** | | |
| 换线 | **100%** | | |
| 搬运 | 95.2% | | |
| 状态查询 | **100%** | | |
| 装配 | **100%** | | |
| 质检 | 96.7% | | |

**微调后模型已达标（96.7% > 88%）。** 剩余错误集中在 `异常应对` 的 `time_window` 数值偏差（如 800ms→1000ms）和少量 object 辨识问题，这些都是槽位填充的精度问题，方向正确。

---

## 👤 User

我做过图像分类的任务，明白监督学习的模型训练过程，但我没接触过大模型及微调，请你结合本项目代码为我深入浅出地讲解该任务中的QloRA微调训练部分

---

## 🤖 Claude

好，让我结合本项目代码，从你熟悉的监督学习视角，一步步把 QLoRA 微调讲透。

---

# QLoRA 微调：从监督学习到 LLM 微调

## 1. 你已理解的部分 → 直接映射

你在图像分类里做的是这样的：

```
输入(图片) → 模型(ResNet/CNN) → 输出(类别) → 算 loss → 反向传播 → 更新全部参数
```

本项目做的事情本质上一模一样：

```
输入(工人话语+场景JSON) → 模型(Qwen3-VL-8B) → 输出(结构化JSON) → 算 loss → 反向传播 → 更新参数
```

**唯一的区别**在于「更新参数」这一步——为什么不能像 ResNet 那样直接把 8B 参数全更新了？

## 2. 为什么不能全量微调？

Qwen3-VL-8B 有 **87.8 亿参数**，如果全量微调：

```
fp32: 8.78B × 4 bytes = 35 GB  ← 仅模型权重
bf16: 8.78B × 2 bytes = 17.6 GB

加上优化器状态（Adam 需要存 momentum + variance）:
训练显存 ≈ 17.6 × 4 = 70 GB  ← 远超 5090 的 32G
```

你跑 ResNet 才几十 MB，所以可以直接 update 全部权重。但 8B 参数意味着你需要三招技巧叠加，这就是 QLoRA：

```
QLoRA = 4-bit 量化 + LoRA 低秩适配 + 训练优化技巧
```

## 3. 第一招：4-bit 量化（为什么叫 **Q**LoRA）

```python
# trainer.py 行 125-130
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,                          # 数据只占 0.5 byte/参数
    bnb_4bit_quant_type="nf4",                  # NormalFloat4，特殊编码方式
    bnb_4bit_compute_dtype=torch.bfloat16,      # 但计算时转回 bf16，保证精度
    bnb_4bit_use_double_quant=True,             # 对量化器本身再做一次量化
)
```

**类比**：JPEG 压缩图片。存储时用有损压缩省空间，但解码显示时尽量还原。

| 精度 | 每参数 | 8B 模型占用 | 类比 |
|------|-------|------------|------|
| fp32 | 4 byte | 35 GB | RAW 格式照片 |
| bf16 | 2 byte | 17.6 GB | PNG 无损压缩 |
| **4-bit NF4** | **0.5 byte** | **~5 GB** | **JPEG 有损但人眼看不出来** |

关键细节——**NF4** 不是均匀量化（0/1/2/3...15），而是假设权重服从正态分布，在密集区域分配更多量化点，稀疏区域少分：

```
均匀量化:  |0|1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|
           ↑ 所有区间等宽，浪费在极值上

NF4:  ||||||||||    |    |    |       |         |
      ↑ 在权重密集的中心区域（μ±σ）量化更细，长尾粗糙
```

结果是「存的时候用 4-bit，算的时候解压回 bf16 算，梯度回传也是 bf16 精度」。所以你会看到：

```python
# trainer.py 行 142-145
model = prepare_model_for_kbit_training(
    model,
    use_gradient_checkpointing=True,            # ← 第三招的一部分
)
```

这行代码做的事：给 4-bit 的 Linear 层装上钩子，确保 forward 时自动「解压→bf16 计算→存回 4-bit」这条流水线正确运转——并且梯度能通过 4-bit 层回传。

## 4. 第二招：LoRA（Low-Rank Adaptation，低秩适配）

4-bit 让模型**能加载进显存**了，但还是不能训练——因为量化权重自身需要被冻结才能保持 bf16→4bit 的对应关系。那参数从哪里来学？

这就是 LoRA 的核心洞察：**不修改原有权重 W，在旁边挂两个小矩阵 A 和 B，只训练它们**。

### 矩阵分解的直觉

```
一个 4096×4096 的全连接层有：4096×4096 = 16,777,216 个参数

LoRA 不直接学 ΔW（形状 4096×4096），而是学：
  A: 4096×16   (65,536)
  B: 16×4096   (65,536)
  总共: 131,072 参数  ← 只有原来的 0.78%！
```

为什么可以这样？因为「微调导致的变化」ΔW 虽然是 4096×4096 的大矩阵，但它的**秩很低**——大部分变化可以用少数几个主方向描述。就像一张照片虽然百万像素，但主要信息可以用几十个主成分近似。

### 前向传播过程

```
h = W·x + ΔW·x
  = W·x + (B·A)·x    ← B(4096×16) × A(16×4096) = ΔW(4096×4096)
  
  冻结部分: W (4-bit 量化，不更新)
  训练部分: A, B (bf16，正常更新)
```

就像在已有的高速公路网（W）旁边修两条小路（B·A），主路不动，只铺设小路来微调目的地。

### 本项目配置

```python
# config.py 行 29-38
@dataclass
class LoRAConfig:
    r: int = 16              # ← 秩，即 A 和 B 中间那维。越大越灵活（16 是性价比甜点）
    lora_alpha: int = 32     # ← 缩放因子，实际 lr 还要乘以 alpha/r = 32/16 = 2
    lora_dropout: float = 0.05
    target_modules: List[str] = ["q_proj", "k_proj", "v_proj", "o_proj"]  # ← 只挂在注意力的 Q/K/V/O 上
```

`target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]` 的意思是**只在 Transformer 的自注意力层上挂 LoRA**，前馈网络（FFN）不动。这是因为自注意力层负责「理解关系」，是对语义最敏感的地方。

最终效果：

```
trainable params: 15,335,424  ← 0.17% 的参数
all params: 8,782,459,120
trainable%: 0.1746

LoRA 适配器大小: ~70 MB  ← 对比：整个模型 16 GB
```

这就是为什么你可以在 5090 上训练：显存里确实有 8.8B 参数，但只有 15M 个参与梯度计算。

## 5. 第三招：训练优化技巧

4-bit + LoRA 还差一口气，需要配套技巧：

### 5a. Gradient Checkpointing（梯度检查点）

```python
# config.py 行 57
gradient_checkpointing: bool = True
```

反向传播时，正常需要存每一层的激活值（activations）用于计算梯度，这很占显存。

Gradient Checkpointing 的做法：**forward 时不存中间激活，backward 时重新 forward 算一遍**。用时间换空间。

```
没有 checkpointing: 显存  ←→ 存中间激活 + 梯度，显存撑爆
有 checkpointing:   显存  ←→ 只存检查点，其他用时重算，省 30-40% 显存
```

### 5b. Paged AdamW 8-bit

```python
# config.py 行 56
optim: str = "paged_adamw_8bit"
```

普通 Adam 需要为每个参数存两个状态（momentum + variance），各 4 byte。15M 可训参数 → 15M × 8 = 120 MB，这还好。

但优化器状态也用 8-bit 量化存储，进一步压缩。`paged` 的意思是当显存不够时，可以把优化器状态换出到 CPU 内存（类似 OS 的虚拟内存分页）。

### 5c. 梯度累积

```python
# config.py 行 45-46
per_device_train_batch_size: int = 2          # 实际每步只放 2 条样本
gradient_accumulation_steps: int = 8          # 但累积 8 步再更新一次
```

```
Step 1: batch(2 samples) → forward → backward → 存梯度，不更新
Step 2: batch(2 samples) → forward → backward → 存梯度，不更新
...
Step 8: batch(2 samples) → forward → backward → 存梯度，执行 optimizer.step()！

等效 batch_size = 2 × 8 = 16
```

这样你实际只用 2 条样本的显存，但获得了 16 条样本的梯度质量。

## 6. 数据管线：从样本到 loss

### 6a. ChatML 渲染

```python
# trainer.py 行 64-86
def render_sample(sample: Dict) -> str:
    user_text = f"工人说: {sample['worker_utterance']}\n\n请输出 JSON:"
    assistant_text = json.dumps(sample["expected_output"], ensure_ascii=False)

    chat = (
        f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
        f"<|im_start|>user\n{user_text}<|im_end|>\n"
        f"<|im_start|>assistant\n{assistant_text}<|im_end|>"
    )
    return chat
```

一条样本渲染后长这样：

```
<|im_start|>system
你是一个工业机器人指令理解助手。请根据工人说的话，输出严格 JSON ...
<|im_end|>
<|im_start|>user
工人说: 把那个蓝色的螺丝放到左边第二个盒子里
请输出 JSON:
<|im_end|>
<|im_start|>assistant
{"action": "取料放置", "object_filter": {"color": "蓝色"}, ...}
<|im_end|>
```

### 6b. Assistant-Only Loss Mask（最关键的设计）

```python
# trainer.py 行 179-191
assistant_marker = processor.tokenizer.encode(
    "<|im_start|>assistant\n", add_special_tokens=False
)
labels = [-100] * len(input_ids)  # ← -100 = PyTorch 的 "忽略此 token"

for i in range(len(input_ids) - marker_len + 1):
    if input_ids[i:i + marker_len] == assistant_marker:
        start = i + marker_len
        for j in range(start, len(input_ids)):
            labels[j] = input_ids[j]      # ← 只有 assistant 部分的 token 参与 loss
        break
```

**为什么？** 和你做图像分类不同，语言模型的训练数据是这样构造的：每个 token 都预测下一个 token。如果我们对所有 token 算 loss：

```
<|im_start|>system\n你是一个工业机器人指令理解助手...  ← 系统提示
<|im_end|>\n<|im_start|>user\n工人说: 把那个蓝色的螺丝... ← 用户输入
<|im_end|>\n<|im_start|>assistant\n{"action": "取料放置"... ← 模型输出
                                           ↑ 只对这里算 loss！
```

如果让 system + user 部分也参与 loss，模型会学习「如何复述系统提示词」和「如何模仿工人说话」，而不是「如何根据指令输出 JSON」。这就像你训练一个分类器却让它同时学数据增强的随机参数——它在学无关的东西。

所以 labels 矩阵长这样：

```
token:   <|im_start|> system\n 你是...  <|im_end|>  <|im_start|> user\n 工人说: ...  <|im_end|>  <|im_start|> assistant\n  {"  action  ":
label:   -100 -100 -100 -100 -100 -100 -100 -100 -100 -100 -100 -100 -100 -100 -100  {"  action  ":
                                                                                       ↑ 从这里开始才不是 -100
```

`-100` 是 PyTorch `CrossEntropyLoss` 的特殊值——`ignore_index`，对应位置的梯度直接置零，不参与 loss 计算。

## 7. 完整数据流：前向 + 反向

把整个过程串起来：

```
┌─────────────────────────────────────────────────────────┐
│ 训练一个 Step                                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. 渲染: worker_utterance → ChatML 字符串               │
│                      ↓                                   │
│  2. 分词: tokenizer → input_ids [1, 2, 3, ...]         │
│                      ↓                                   │
│  3. Mask: 标记 assistant 起始位置 → labels               │
│           system/user 部分 labels = -100                  │
│           assistant 部分 labels = input_ids              │
│                      ↓                                   │
│  4. Forward:                                             │
│     ┌──────────────────┐                                │
│     │ W_q (4bit+Lora)  │ ← 解压 → bf16 → + (B_q·A_q)·x │
│     │ W_k (4bit+Lora)  │   同样流程                       │
│     │ W_v (4bit+Lora)  │                                 │
│     │ W_o (4bit+Lora)  │                                 │
│     │ FFN (4bit,冻结)  │ ← 只用 4bit，不挂 LoRA          │
│     └──────────────────┘                                │
│                      ↓                                   │
│     output logits: [seq_len, vocab_size]                │
│     每个位置预测下一个 token 的概率分布                    │
│                      ↓                                   │
│  5. Loss: CrossEntropy(logits, labels)                  │
│     labels中=-100的位置被自动忽略                         │
│     只对 assistant 部分的 token 算 CE loss               │
│                      ↓                                   │
│  6. Backward:                                            │
│     loss 反传 → 只更新 LoRA 的 A、B 矩阵                   │
│     W (4bit) 权重不更新                                  │
│     FFN 权重不更新                                        │
│                      ↓                                   │
│  7. 累积 N 步 → optimizer.step() 更新 LoRA 参数          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 8. 训练曲线解读

你刚才跑出来的结果：

```
初始 loss: 0.30
收敛 loss: 0.02~0.04
```

这和图像分类不同——语言模型的 loss 是 **per-token cross-entropy**。e^loss ≈ 困惑度（perplexity）：

```
loss=0.30 → 困惑度 ≈ e^0.30 = 1.35  ← 每个位置平均在 1.35 个选项中犹豫
loss=0.02 → 困惑度 ≈ e^0.02 = 1.02  ← 几乎确定性地选对
```

0.02 这个值说明模型基本把 JSON 格式、action 类型、字段名都背熟了。因为训练数据中 JSON schema 高度重复，模型很快就学会了输出格式。**真正的挑战不是格式（loss 低），而是槽位填充的准确性（eval 分数高）。**

这就是为什么 loss 降到 0.02 但 eval 只有 96.7%——剩余 3.3% 的错误来自「物体辨识」（螺母 vs 接线柱）和「数值偏差」（800ms vs 1000ms），这些是训练模板覆盖不到的边界 case。

## 9. 与全量微调（ResNet 分类场景）的区别总结

| | ResNet 分类 | QLoRA 微调 Qwen3-VL |
|------|-------------|-------------------|
| 参数规模 | ~25M | ~8,782M |
| 更新参数 | 全部 25M | 仅 15M (LoRA) |
| 参数精度 | fp32 | 4-bit NF4 |
| 显存占用 | ~2 GB | ~15-18 GB |
| Loss 类型 | CE（类别概率） | CE（per-token，含 ignore_index） |
| 优化器 | Adam (fp32) | Paged AdamW 8-bit |
| 输出文件 | checkpoint.pth (~100MB) | adapter_model.safetensors (~70MB) |

本质上，**QLoRA 就是给一个冻结的巨型 Transformer 网络挂上几根可训练的「细线」（低秩矩阵），只调这些线来适应你的任务**。核心智慧和你在分类里用 Fine-tune vs Feature Extract 的逻辑是一样的——只不过因为规模不同，你需要 4-bit 量化 + 低秩分解这两个工程手段才能把它塞进 32G 显存。

---

## 👤 User

先只着重讲解一下4bit量化部分，你可以围绕我下面的几个疑问展开，一是讲清一下几种数据精度，二是有关模型的加载这个概念，以及训练时和显存的关系或者所有数据在显存的流转过程，主要是讲清数据与显存的关系吧，三是4-bit量化本身更加深入的讲解一下，比如上一个回答中有关是否均匀量化以及存，算，回传具体的概念等，希望你能明白我的疑点

---

## 🤖 Claude

好，这三个问题问得很准，我逐一深入。

---

# 4-bit 量化深度讲解

## 一、数据精度：到底在说什么

你跑图像分类时可能没太在意精度——PyTorch 默认 fp32，一张 224×224 的图不过几 MB，没人计较这个。但到了 8B 参数的模型，精度直接决定你能不能跑。

### 本质：浮点数怎么存的

所有精度都是 IEEE 754 标准的变体。浮点数 = 符号位 + 指数位 + 尾数位：

```
fp32 (32-bit):
┌───┬─────────┬───────────────────────┐
│ S │ exp(8)  │      mantissa(23)      │
└───┴─────────┴───────────────────────┘
范围: ~±3.4×10³⁸, 精度: ~7位有效数字
每参数: 4 bytes

fp16 (16-bit):
┌───┬─────────┬───────────┐
│ S │ exp(5)  │ mant(10)  │
└───┴─────────┴───────────┘
范围: ~±65504, 精度: ~3位有效数字
每参数: 2 bytes
问题: 最大值只有65504，梯度容易溢出

bf16 (16-bit, Google Brain Float):
┌───┬─────────┬───────────┐
│ S │ exp(8)  │ mant(7)   │  ← 和fp32相同的指数位！
└───┴─────────┴───────────┘
范围: ~±3.4×10³⁸ (和fp32一样), 精度: ~2位有效数字
每参数: 2 bytes
设计思路: 牺牲精度保范围。对大模型来说，梯度值域比精度重要
```

**本项目用 bf16 的原因就一句话**：指数和 fp32 一样宽（8 bit），梯度不会因为超出 65504 而溢出成 NaN，训练不会崩。

### 整数精度（量化用）

```
int8: -128 到 127，256个离散值
int4: -8 到 7，16个离散值

关键理解: fp32→int4 不是简单的截断，需要「映射」
```

### 各精度在本项目的角色

```python
# config.py 行 62-66
@dataclass
class BitsAndBytesConfig:
    load_in_4bit: bool = True              # 存储: 权重以 4-bit 存在显存
    bnb_4bit_quant_type: str = "nf4"       # 编码: 用 NormalFloat4，非常规 int4
    bnb_4bit_compute_dtype: str = "bfloat16" # 计算: 实际乘法用 bf16
    bnb_4bit_use_double_quant: bool = True  # 二次压缩: 量化参数本身也量化
```

| 精度 | 用在哪 | 为什么 |
|------|--------|--------|
| **4-bit NF4** | 模型权重存储 | 省显存（4GB vs 16GB） |
| **bf16** | 前向/反向计算 | 指数范围大，不溢出 |
| **bf16** | LoRA 的 A/B 矩阵（可训参数） | 需要梯度，不能量化 |
| **8-bit** | 优化器状态（Paged AdamW） | 省显存但保持动量精度 |
| **fp32** | 极少部分（如 LayerNorm） | 这些层对精度敏感 |

---

## 二、模型加载 & 显存流转

### 2a. "加载模型"到底发生了什么

```python
# trainer.py 行 134-138
model = Qwen3VLForConditionalGeneration.from_pretrained(
    model_path,                              # ← 硬盘上的 .safetensors 文件
    quantization_config=bnb_config,          # ← "加载时顺便压缩成 4-bit"
    device_map="auto",                       # ← 自动分配到 GPU
    torch_dtype=torch.bfloat16,              # ← 非量化层的默认精度
)
```

这行代码背后发生的事：

```
硬盘 (/root/autodl-tmp/model_cache/qwen/...)
│
│  16GB 的 .safetensors 文件（原始 bf16 权重）
│
└──→ CPU 内存
     │
     │  torch.load() 把文件读入 CPU RAM
     │  此时权重仍是 bf16: 每个参数 2 bytes
     │
     └──→ 量化 → GPU 显存
          │
          │  BitsAndBytes 在这一步把 bf16 → NF4:
          │  W_4bit = quantize(W_bf16)
          │  每个参数: 2 bytes → 0.5 byte
          │
          └── 最终: ~4-5 GB 占用 GPU 显存
```

`device_map="auto"` 的作用：如果一个大模块一张卡放不下，自动切成多份跨卡。48G 显存的卡够放，所以全在 GPU 上。

### 2b. 训练时一个 step 的完整显存流转

这是你图像分类经验里没有的部分——因为 ResNet 的中间激活几十 MB，可以被忽略。但 8B LLM 的一个 step，显存里同时住着好几样东西：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step N 的显存全景（以本项目为例）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌──────────────────────────────────────────┐
│  ① 模型权重 (4-bit 存储)        ~4.4 GB  │  ← 冻结，不更新
│     ├ W_q, W_k, W_v, W_o 各层            │
│     ├ FFN 各层                            │
│     └ Embedding, LayerNorm (bf16)        │
├──────────────────────────────────────────┤
│  ② LoRA 适配器 (bf16)          ~0.06 GB  │  ← 训练，需梯度
│     ├ A_q, B_q (W_q 的旁路)              │
│     ├ A_k, B_k                           │
│     ├ A_v, B_v                           │
│     └ A_o, B_o                           │
├──────────────────────────────────────────┤
│  ③ 优化器状态 (8-bit Paged)     ~0.24 GB  │  ← 存动量+方差
│     15M 参数 × 2 状态 × 1 byte          │
├──────────────────────────────────────────┤
│  ④ 中间激活 (bf16)              ~5-8 GB  │  ← Forward 时产生的中间值
│     每层的 hidden states, attention    │
│     scores, 残差连接...                  │
├──────────────────────────────────────────┤
│  ⑤ 梯度缓存                     ~0.5 GB  │  ← Backward 时存
├──────────────────────────────────────────┤
│  合计                           ~15-18GB │  ← 刚好塞进 32G/48G
└──────────────────────────────────────────┘
```

**Forward 时**的显存峰值在中间激活（④）。32 层 Transformer，每层都产生大量中间向量，这是大头。

**Backward 时**，④ 里的激活值被逐个消费计算梯度，梯度存进 ⑤。

**Optimizer.step() 时**，只更新 ② 里的 LoRA 参数，③ 更新动量/方差。

这就是为什么最终 15-18G——大头是激活值和 4-bit 权重，LoRA 本身反而很小。

### 2c. 为什么 Gradient Checkpointing 能省那么多

```python
# config.py 行 57
gradient_checkpointing: bool = True
```

```
没有 checkpointing:
  Forward: 算第1层→存激活→算第2层→存激活→...→算第32层→存激活
  显存: 同时存着 32 层的所有中间激活 (~12 GB)

有 checkpointing:
  Forward: 只存「检查点」(每 1-2 层存一个)，其余用完就扔
  Backward 到第 15 层时: 发现激活被扔了 → 从最近的检查点重新 forward 第 15 层

  时间: 多了 ~20% (重新 forward)
  显存: 省了 ~40% (不用存全部激活)
```

等同于「我不记笔记，需要的时候翻书重读」。翻书花时间，但笔记本轻了。

---

## 三、4-bit 量化深入

### 3a. 常规 int4 vs NF4：均匀 vs 非均匀

**常规 int4 均匀量化**：

```
bfloat16 权重: [-3.2, -1.8, -0.3, 0.0, 0.5, 1.2, 2.7, 4.1, ...]
                  ↓
Step 1: 找最大最小值 → max=4.1, min=-3.2, range=7.3
Step 2: 把 range 切成 16 等份:
         -3.2 -2.73 -2.27 -1.80 -1.33 -0.87 -0.40 0.07 0.53 1.00 1.47 1.93 2.40 2.87 3.33 3.80
Step 3: 每个权重映射到最近的分割点:
         -3.2→0, -1.8→3, -0.3→6, 0.0→7, 0.5→8, 1.2→9, 2.7→12, 4.1→15

存储: [0, 3, 6, 7, 8, 9, 12, 15]  ← 每个只用 4 bit
使用时: lookup[0] = -3.2, lookup[3] = -1.80, ...
```

问题：均匀量化假设权重在 [-3.2, 4.1] 上均匀分布，但**神经网络权重大概率是正态分布**：

```
权重的实际分布（正态曲线）:
         ██
        ████
       ██████         ← 绝大多数权重集中在均值附近 (~0)
      ████████
     ██████████
    ████████████
   ██████████████
──┼───┬───┬───┬───┬───┬──
-3  -2  -1   0   1   2   3

均匀量化的问题:
区间 [-0.4, +0.4] 里挤了 80% 的权重
但只分到 2-3 个分割点（因为这区间只占全范围的 11%）
→ 量化误差大！很多不同的值被压缩成一个

NF4 的做法:
在密度高的区域（0 附近）分配更多分割点
在密度低的区域（±3σ）分配更少
→ 同样的 16 个值，信息损失更小
```

**NF4 的 16 个量化级别长这样**（具体值来自 Dettmers 的论文，经过数学优化）：

```
NF4 分割点: [-1.0, -0.696, -0.525, -0.395, -0.284, -0.188, 
             -0.101, -0.018, 0.018, 0.101, 0.188, 0.284, 
              0.395, 0.525, 0.696, 1.0]
              
注意: 0 附近的间距 ~0.08, 边缘间距 ~0.3  ← 密度自适应！
```

这 16 个值不是均匀的 —— 它们是标准正态分布的各分位数。本质上是对「假设权重服从 N(0,1)」的最优离散化，就像 JPEG 对人眼敏感的频率多分配 bit。

### 3b. 分块量化：不是全局一组的

一个细节：不是把 8B 参数当成一个整体去找 min/max，而是**每个 64 参数的块独立量化**：

```
W_q 层 (4096×4096):
  ┌──────────┐
  │ 64个参数  │ → 算自己的 max/min → 16个分割点 → 4-bit 编码
  ├──────────┤
  │ 64个参数  │ → 算自己的 max/min → 16个分割点 → 4-bit 编码
  ├──────────┤
  │   ...    │
  └──────────┘

为什么分块？
  全局量化: 一个 outlier (w=50.0) 会把整个 range 撑大
            所有正常权重都被挤进 1-2 个分割点 → 全毁了
  分块量化: outlier 只污染它自己那 64 个参数所在的块
            其他块不受影响
```

### 3c. 存（storage）vs 算（compute）vs 回传（gradient）

这是最容易被误解的地方。我给你画清楚：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  一个 QLoRA 层的完整 forward+backward
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Forward:
─────────
  输入 x (bf16) 
      │
      ▼
  ┌─────────────────────────────┐
  │ W_4bit (显存中的 4-bit 权重)  │  ← 存: 0.5 byte/param
  │      ↓ dequantize            │
  │ W_bf16 = lookup[W_4bit]      │  ← 算: 查表，恢复成 bf16
  │      ↓                       │     
  │ y1 = W_bf16 @ x              │  ← 算: bf16 矩阵乘法 (正常精度)
  │                              │
  │ LoRA 旁路:                    │
  │ A (bf16) 尺寸 [4096, 16]     │  ← 存: 2 byte/param (可训)
  │ B (bf16) 尺寸 [16, 4096]     │  ← 存: 2 byte/param (可训)
  │ Δy = B @ A @ x               │  ← 算: bf16 矩阵乘法
  │                              │
  │ y = y1 + Δy                  │
  └─────────────────────────────┘
      │
      ▼
  输出 y (bf16) → 进入下一层


Backward:
──────────
  ∂L/∂y (bf16) 从上一层传下来
      │
      ▼
  ┌─────────────────────────────┐
  │ LoRA 旁路梯度:                │
  │ ∂L/∂A = B^T @ ∂L/∂y @ x^T   │  ← A 和 B 是 bf16，正常反向传播
  │ ∂L/∂B = ∂L/∂y @ (A@x)^T     │  ← 这些梯度是 bf16，参与更新
  │                              │
  │ 主路梯度（给 x 的）:          │
  │ ∂L/∂x = W_bf16^T @ ∂L/∂y    │  ← W_bf16 是从 4-bit 解压出来的
  │   + B^T @ A^T @ ∂L/∂y       │    在这个计算中它是 bf16，有梯度流过
  │                              │    但梯度只到 dequantize 就停了
  │                              │
  │ 4-bit 权重的梯度:              │
  │ ❌ 不计算！W_4bit 是离散整数  │  ← 离散值没有导数概念
  │ ❌ 不更新！                   │     梯度停在 dequantize 操作之前
  │                              │     W_4bit 在整个训练中完全不变
  └─────────────────────────────┘
      │
      ▼
  ∂L/∂x (bf16) → 传给上一层

  
Optimizer.step():
──────────────────
  只更新 A 和 B:
    A_{new} = A - lr * ∂L/∂A
    B_{new} = B - lr * ∂L/∂B
  
  W_4bit: 不动
  
  8-bit 优化器状态也更新:
    momentum_A = β * momentum_A + (1-β) * ∂L/∂A    ← 8-bit 存
    variance_A = β * variance_A + (1-β) * (∂L/∂A)²  ← 8-bit 存
```

### 3d. Straight-Through Estimator（STE）：梯度怎么穿过量化层

你可能在困惑：dequantize 是离散查表操作，导数要么 0 要么不存在，梯度怎么传回去给 x？

这是整个量化训练的核心技巧——**STE（直通估计器）**：

```python
# 伪代码：STE 的逻辑
def dequantize_and_backward(W_4bit, x):
    # Forward: 正常查表
    W_bf16 = lookup_table[W_4bit]    # 离散查表，梯度为 0
    y = W_bf16 @ x
    
    # Backward: STE 把梯度「跳过」离散操作
    # ∂L/∂W_4bit 不计算（W_4bit 冻结）
    # ∂L/∂x 用 W_bf16 算，假装 dequantize 是直通的
    # 即: 反向时把 dequantize 当成恒等映射
    
    return y
```

```
直觉理解: 
  离散阶梯 → Forward 走阶梯，Backward 走斜坡（忽略台阶）
  
  Forward:    ┌─┐              ← 实际是离散的
              │ │
          ┌─┐ │ │
          │ │ │ │
      ┌─┐ │ │ │ │
      │ │ │ │ │ │
  ──┘ └─┘ └─┘ └─┘
      -1  0   1   2

  Backward:                    ← 但梯度假装它是连续的
              /
            /
          /
        /
      /
  ──┘
```

**为什么这能 work？** 因为 Wi_4bit 虽然在单个 step 不更新，但 LoRA 的 A 和 B 是连续值，它们接收了来自 x 方向的完整梯度（通过 STE），所以能学到补偿量化误差的方向。多步积累后，A·B 自然趋近于「理想 ΔW 但被量化裁掉的部分」。

### 3e. Double Quantization：量化的量化

```python
bnb_4bit_use_double_quant: bool = True
```

分块量化意味着每个 64-参数的块需要一个 32-bit 的缩放因子。模型有 8B/64 = 1.25 亿个块 → 1.25 亿 × 4 bytes = 500 MB 只用来存缩放因子。

Double Quantization：对这 1.25 亿个缩放因子再做一次 8-bit 量化：

```
一次量化: 权重(4-bit) + 缩放因子(fp32) → ~4.5 GB
二次量化: 权重(4-bit) + 缩放因子(8-bit) + 缩放因子的缩放因子 → ~4.0 GB
          ↑ 省了 ~0.5 GB
```

就像 JPEG 不光压缩像素，连量化表本身也压缩。

---

### 总结：三件事一条线

| 问题 | 答案 |
|------|------|
| 精度怎么选 | bf16 计算（防溢出），NF4 存储（省 75%），8-bit 优化器（再省一层） |
| 模型怎么"加载" | 硬盘 bf16 → CPU 解压 → 量化成 NF4 → GPU 显存 |
| 训练时显存怎么分配 | 权重 4.4G + LoRA 0.06G + 优化器 0.24G + 激活 5-8G + 梯度 0.5G ≈ 15-18G |
| NF4 vs int4 | NF4 是正态分布最优的 16 个非均匀分割点，比均匀 int4 信息损失小 |
| 存/算/回传的关系 | 存时 4-bit，算时解压 bf16，回传时梯度跳过离散操作（STE）只更新 LoRA |

---

