# Claude Conversation Log

Session ID: 52fc790c-6d5f-4e52-8413-72f8f9f882fe
Date: 2026-06-11 05:44:16

---

## 👤 User

浏览整个文档，写进'/root/Brain/CLAUDE.md'

---

## 🤖 Claude

Now let me read all the source files to understand the full codebase.

---

## 🤖 Claude

Now I have a complete picture of the entire codebase. Let me write the comprehensive CLAUDE.md.

---

## 🤖 Claude

已完成。已浏览整个代码库并将全面的文档写入 `/root/Brain/CLAUDE.md`（281 行）。

以下是新增/扩展的主要内容：

**之前缺失，现已记录：**
- **完整的仓库布局** — 每个文件和目录，包括遗留的根级脚本及其用途，均已记录
- **遗留脚本** — `run_baseline.py`、`baseline_test_v2.py`、`dataset_test.py`、`test_qwen.py`、`check_json.py`、`tojsonl.py`、`download_model.py` — 每个脚本使用的模型、作用以及为何被弃用都进行了说明
- **遗留数据文件** — `for_test.jsonl`、`instruction_dataset_v1.json`、`instruction_datasets_v1.jsonl`
- **业务文档** — PDF 和 Word 文件均已编目
- **数据格式表** — 每个样本中 5 个键的完整规格说明
- **带有具体数值示例的评分公式** — 展示了 must/optional 字段在所有正确、部分缺失和错误情况下的分数变化
- **8 种任务类型表** — 包含 JSON 模式签名和典型话语
- **5 步演示流程** — 逐步分解
- **详细的模块文档** — 每个 `.py` 文件的关键函数、设计选择、CLI 参数以及工作原理
- **模板兼容性系统** — 记录了 `TEMPLATE_COMPAT` 为何存在以及反向构建生成模式
- **环境/依赖项** — 明确的软件包和硬件要求
- **评分参考表** — 取料_放置 任务的快速查阅，包含 6 种分数场景

---

## 👤 User

我们重新看一下这个run_demo.py，你给我好好梳理一下流程

---

## 🤖 Claude

好的，我来逐行梳理 `run_demo.py` 的完整流程。

---

## 入口：CLI 解析 (行 329-360)

```
python demo/run_demo.py [--skip-train] [--gen-data] [--interactive]
```

三个 flag 都是 `action="store_true"`，默认 `False`：

| Flag | CLI 不传 | CLI 传入 |
|:---|:---|:---|
| `--skip-train` | `False` → **会训练** | `True` → 跳过训练 |
| `--gen-data` | `False` → 读已有数据 | `True` → 重新生成数据 |
| `--interactive` | `False` → 跑完整流程 | `True` → 交互 REPL |

然后分叉为两条路：

```
if interactive → run_interactive()
else           → run_full_demo(skip_train, gen_data)
```

---

## 路径 A：交互模式 `--interactive` (行 289-323)

```
run_interactive()
  ├─ load_model_with_lora()           # 加载基座模型 + LoRA（如果 final/ 目录存在）
  ├─ while True:                      # REPL 循环
  │   ├─ input("工人说: ")
  │   ├─ 构造 sample:
  │   │   world_state = {             # ⚠️ 硬编码的世界状态
  │   │     objects:    [螺丝(蓝色,十字) obj_001]
  │   │     containers: [工位 box_001(左一), box_002(左二)]
  │   │   }
  │   ├─ predict_single(model, processor, sample)   # 没有传 image_path
  │   └─ 打印 parsed JSON 或 raw_output
  └─ Ctrl+C 退出
```

**问题**：世界状态是硬编码的，只有 1 个螺丝 + 2 个工位。用户输入的指令如果涉及其他物体/容器类型（比如"拧螺母"、"查划痕"、"切产线"），模型会因为世界状态里不存在对应实体而输出不可靠的结果。这个交互模式更像一个快速体验玩具，不适合实际测试。

---

## 路径 B：完整 Demo 流程 (行 121-286)

这是主流程，5 个步骤：

### Step 1 — 数据加载/生成 (行 143-158)

调用 `load_or_generate(TRAIN_FILE, TEST_FILE, gen_data)` (行 61-118)：

```
gen_data=True (--gen-data)
  ├─ 强制重新生成训练集: 56条/任务 × 8 = 448 条 (seed=42)
  ├─ 收集训练集所有 utterance
  └─ 强制重新生成测试集: 13条/任务 × 8 = 104 条 (seed=1041, exclude 训练集话术)

gen_data=False (默认)
  ├─ train_v2.jsonl 存在? → 加载
  │   不存在? → 自动生成 (56/任务)
  ├─ test_v2.jsonl 存在?  → 加载
  │   不存在? → 自动生成 (13/任务, 排除训练集话术)
  └─ 返回 (train_samples, test_samples)
```

然后打印训练集的任务分布（`Counter` 每种 task_type 的样本数）。

### Step 2 — 基线测试 (行 160-185)

```
load_model_with_lora(base_path=MODEL_PATH, lora_path=None)
  └─ Qwen3-VL-8B-Instruct 以 bfloat16 全精度加载（不是 4bit！）
     ⚠️ 这一步显存占用 ~16GB

predict_batch(model, processor, test_samples, batch_size=4)
  └─ 贪心解码 (do_sample=False)，每批 4 条

evaluate_dataset(baseline_preds, test_samples)
  └─ 严格字段匹配，输出基线分数

del model + torch.cuda.empty_cache()
  └─ 释放显存，为 Step 3 训练腾空间
```

### Step 3 — QLoRA 微调 (行 187-209)

```
skip_train=True?
  ├─ Yes → 跳过，记录 status: "skipped"
  └─ No  → train(train_file=TRAIN_FILE)
            ├─ 4bit NF4 量化加载基座模型 (~4-5GB)
            ├─ 挂 LoRA adapter (r=16, target=q/k/v/o_proj)
            ├─ 训练 3 epochs, batch=2×8=16
            └─ 返回 lora_path = outputs/lora_out/final/
```

### Step 4 — 微调后推理 (行 211-235)

```
lora_path 存在?
  ├─ Yes → load_model_with_lora(base_path, lora_path=lora_path)
  │         └─ 全精度加载 + 挂 LoRA adapter
  │        predict_batch(model, processor, test_samples)
  └─ No  → tuned_preds = baseline_preds  (退化到基线结果)

evaluate_dataset(tuned_preds, test_samples)
```

### Step 5 — 对比报告 (行 237-285)

```
baseline_score vs tuned_score → improvement = tuned - baseline

打印:
  ┌──────────────────────────────────────┐
  │  数据集: 训练 448 条 / 测试 104 条    │
  │  基线均分:   80.5%                    │
  │  微调后均分: 92.3%                    │
  │  提升幅度:   +11.8%                   │
  │  是否达标:   ✅ 达标                  │
  └──────────────────────────────────────┘

保存 → outputs/demo_report.json
打印一条样例的完整推理链路 (utterance → parsed → expected → score)
```

---

## 5 种执行路径总结

```
python run_demo.py                          全流程: 加载数据 → 基线 → 训练 → 推理 → 报告
python run_demo.py --skip-train             基线+评测: 加载数据 → 基线 → (跳过训练) → 退化报告
python run_demo.py --gen-data               重新生成数据后跑全流程
python run_demo.py --gen-data --skip-train  仅生成数据 + 跑基线
python run_demo.py --interactive            交互 REPL (硬编码 world_state)
```

---

## 我发现的问题

**1. `--mock` 参数不存在。** README 和旧 CLAUDE.md 里都写了 `python run_demo.py --mock`，但代码里根本没有这个参数。需要删掉文档引用，或者在代码里加回去。

**2. 交互模式的世界状态硬编码。** 只有 `蓝色螺丝` + `左一/左二` 两个工位，用户说"检查零件划痕"或"切到3号线"时，模型会因为 world_state 不匹配而输出不可靠的结果。

**3. Step 2 先用全精度加载模型跑基线，然后删掉；Step 3 再用 4bit 加载跑训练。** 两次加载，浪费启动时间。如果 `--skip-train`，Step 2 的基线推理用全精度（浪费显存），但并没有在 demo_report.json 的 baseline 中反映出来——上次的报告显示 `avg_score: 0.8049`，`format_pass_rate: 1.0`，说明基座模型在 JSON 格式输出上其实表现不差，只是字段值容易错。

**4. `run_full_demo` 函数签名的默认值** (`skip_train=True, gen_data=True`) 和 CLI 传参的默认值 (`False, False`) 是反的。虽然 CLI 总是传参覆盖，但如果有人 `import` 调用会中招。

需要我修这些问题吗？

---

## 👤 User

先别急，我跑了一下，我看到，速度很快，且精度很高，我怀疑这个代码是不是有cheating？并且对数据集的格式我还有疑问，是否需要引入图像？我们先纵览一下大问题

---

## 🤖 Claude

好问题。让我仔细排查。

---

## 🤖 Claude

好的，让我从三个层面来拆：**为什么这么快且准（cheating 嫌疑）**、**数据集的根本问题**、**图像的定位**。

---

## 一、为什么又快又准？四层 "leakage"

### Cheating #1：训练集和测试集共享同一个模板池

```python
# 训练集
train = generate_dataset(n_per_task=56, seed=42)
# 测试集
test  = generate_dataset(n_per_task=13, seed=1041, exclude_utterances=train_utts)
```

唯一的"隔离"是 utterance 级别的去重。但底层的模板是一个池子：

```
训练时模型看到:   "把{蓝色}{螺丝}放到{左一}"        → action=取料_放置, color=蓝色, ...
测试时模型看到:   "把{红色}{螺母}放到{工位3}"       → action=取料_放置, color=红色, ...
                   ^^^^^^^^ 完全相同的模板结构 ^^^^^^^^
```

模型不是在"理解指令"，是在**做模板匹配 + 槽位填充**。这解释了为什么基线（零微调）就能拿 80.5%——Qwen3-VL 基座模型本来就擅长这种文本抽取 + 查表替换。

### Cheating #2：反向构建保证了 utterance ↔ expected_output 完美对应

```python
# data_generator.py 行 680-697
# 2. 先生成 expected_output（确定所有随机值）
expected = _build_expected_output(task_type, objects, containers)

# 3. 从 expected_output 反向构建 utterance 上下文
ctx = _build_utterance_context(task_type, expected, objects, containers)

# 4. 选模板、填槽
utterance_tpl = random.choice(candidates)
worker_utterance = fill_template(utterance_tpl, ctx)
```

**先决定答案，再反向造句。** 这保证了 utterance 中一定包含 `expected_output` 所需的全部信息——零歧义、零缺失、零冗余。真实工厂里工人说话是："哎那个啥，蓝色的那个，放那边去"。现在这个数据集是纯净的教科书。

### Cheating #3：world_state 以纯文本 JSON 喂给模型

```
世界状态: {"objects":[{"id":"obj_315","type":"轴承","color":"银色",...}], 
          "containers":[{"id":"box_510","type":"料盒","position":"右二",...}]}

工人说: 把银色轴承拣出来，送到右二
请输出 JSON:
```

模型的任务退化为：
1. 从 utterance 提取关键词 "银色"、"轴承"、"右二"
2. 在 world_state JSON 里搜索匹配 `color=银色, type=轴承` 的 object → `obj_315`
3. 搜索 `position=右二` 的 container → `box_510`
4. 填进 JSON schema

这是**槽位填充（slot filling）**，不是自然语言理解。Qwen3-VL 的文本匹配能力足够应付，不需要微调。

### Cheating #4：eval_criteria 设的门槛太低

以取料_放置为例：

```
must_match: [action, object_filter.color, target.container]  ← 3 个字段
optional:   [object_filter, source, target, force]            ← 4 个字段
```

**模型即使完全不输出 `source`（物体 id），也能拿多少分？**

```
score = (3 must 全对 + 0.5 × 0 optional) / (3 + 0.5 × 4) = 3/5 = 0.6
```

再看其他任务类型：

| 任务 | must_match 关键字段 | 可以完全忽略的字段 |
|:---|:---|:---|
| 搬运 | `action, target_location` (2个) | `object`（物体 id 错了不扣分！） |
| 质检 | `action, check_type, expected_answer` | `object`（检哪个物体不管） |
| 换线 | `action, line_id` | `model`（型号随便编） |
| 异常应对 | `action, urgency` | `response_window_ms`（响应窗口随便编） |

**搬运任务只要说出目的地 "A区传送带" 就能拿高分——具体搬的是哪个物体，错了也不怎么扣。**

---

## 二、图像问题：Qwen3-**VL** 被用成了纯文本模型

```
基座模型: Qwen3-VL-8B-Instruct
           ^^ 视觉语言模型，但从来没传过图像
```

推理代码里有图像桩：
```python
if image_path:
    user_content.append({"type": "image", "image": image_path})
```

但所有调用路径都 `image_path=None`，从不传图。系统提示词里却写着：

> "必须严格依据工人说的话、世界状态**以及看到的图片**进行判断"

这句话是在**撒谎**——模型根本没看到图片。

### 两条路，必须选一条：

| 路线 | 方案 | 工作量 | 效果 |
|:---|:---|:---|:---|
| **A: 降级模型** | 换 Qwen3-8B（纯文本），参数更少推理更快 | 小 | 维持现状，诚实地做文本模型 |
| **B: 升维数据** | 生成图片（渲染 3D 场景或拍真实产线），让 VL 真正看图理解 | 大 | 质的飞跃，能处理"那个"等指代 |

A 路线适合快速 demo，B 路线才有真正的工业落地价值。当前的"伪 VL"状态是最差的——明明没用图像，却在 prompt 里暗示用了，这对评测和论文都是硬伤。

---

## 三、总结：核心矛盾

```
                   声称的能力                       实际的能力
              ┌──────────────────┐           ┌──────────────────┐
  输入        │ 自然语言 + 图像   │           │ 模板文本 + JSON   │
  理解方式    │ 语义理解          │    VS     │ 槽位填充          │
  泛化范围    │ 任意工人话语      │           │ 模板库内的变体     │
  评测方式    │ 严格 JSON 匹配    │           │ 3/7 字段必须匹配   │
  模型能力    │ 多模态 VL         │           │ 纯文本 LLM         │
              └──────────────────┘           └──────────────────┘
```

**当前系统是一个设计良好的模板槽位填充器，包装成了"工业指令理解系统"。** 要在技术和产品上立得住，至少需要：

1. **测试集模板与训练集彻底隔离** —— 手写一批训练集从未出现过的句式
2. **eval_criteria 收紧** —— `source`/`object` 等关键字段必须是 must_match
3. **图像问题诚实处理** —— 要么加图，要么换纯文本模型，删掉 prompt 里关于"图片"的谎言
4. **world_state 逐步降噪** —— 加入无关物体、歧义指代、缺失信息

要我先针对这些问题做代码修改，还是先讨论优先级？

---

## 👤 User

先把这些现状写进'/root/Brain/CLAUDE.md'

---

## 🤖 Claude

已写入。新增了两个章节：

**`⚠️ Critical assessment: known leakage & limitations`** — 详细记录四项泄漏：

| 泄漏 | 核心机制 | 影响 |
|:---|:---|:---|
| #1 模板池共享 | train/test 用同一套 `TASK_TEMPLATES`，仅 utterance 级去重 | 模型学的是模板→JSON映射，不是泛化理解 |
| #2 反向构建 | 先定 expected_output，再反向造句 | 零歧义、零缺失——退化为槽位填充 |
| #3 world_state 明文 | 推理时喂 JSON 查表 | 模型不需要"理解"，只需要关键词搜索+ID匹配 |
| #4 must_match 太松 | 搬运忽略 object，换线忽略 model | 安全关键字段错了不扣分 |

**`Reality check: what the system actually does`** — 声称 vs 实际对比表，以及四条 minimum fixes。

---

## 👤 User

这个是qwen的视觉-语义模型，后面应该也是需要加视觉输入以及相应训练的，这块怎么做？目前的情况作为demo肯定可以，但是还远远没有达到验收标准

---

## 🤖 Claude

好的，让我从数据、训练、推理三个层面系统分析怎么把视觉加进去。

---

## 🤖 Claude

先看当前训练代码对视觉的兼容状态，再给方案。

---

## 🤖 Claude

好，现在情况清楚了。让我从**数据→训练→推理**三层，给一个完整的视觉升级方案。

---

## 一、先搞清楚当前代码的"四道坎"

当前 `trainer.py` 在三个地方**刻意绕过了视觉能力**：

```
当前流程:
  render_sample()    →  纯文本 ChatML 字符串
  preprocess()       →  processor.tokenizer()  ← 故意绕过多模态 processor
  data_collator()    →  只 pad input_ids/attention_mask/labels
  model.generate()   →  无 pixel_values 输入
```

Qwen3-VL 处理图像的正确路径是：

```
正确流程:
  messages = [{"role":"user", "content":[
      {"type":"image", "image": "path/to/img.jpg"},    ← PIL Image
      {"type":"text",  "text": "工人说: ..."}
  ]}]
  text = processor.apply_chat_template(messages)        ← 自动插入 <|vision_start|><|image_pad|><|vision_end|>
  inputs = processor(text=text, images=[pil_image], ...) ← 同时生成 pixel_values + image_grid_thw
  # inputs = {input_ids, attention_mask, pixel_values, image_grid_thw}
```

三个核心差异：
- **ChatML 里多了 vision tokens**：`<|vision_start|><|image_pad|>...<|image_pad|><|vision_end|>`
- **多了 `pixel_values`**：图像被 ViT patchify 后的张量，shape 取决于动态分辨率
- **多了 `image_grid_thw`**：记录每个图像被切成几行几列的 grid

这四项改造（render_sample → preprocess → data_collator → model.generate）是**训练侧的硬门槛**，每项都必须改。

---

## 二、分阶段路线图

建议分三个阶段，不追求一步到位：

### Phase 1 — 推理先行（1-2 天）

**目标**：不改训练，只让推理链路能处理真实图像。验证 Qwen3-VL 的视觉能力对指令理解到底有没有增益。

**改动范围**：只改 `inference.py` 的 `predict_single()`（代码桩已经有了，补全逻辑），不改 `trainer.py`。

**验证方式**：拍 10 张真实产线照片，手写 utterance，人工看输出质量。

```
不做: 图像训练
只做: 推理时传 PIL Image → 看 Qwen3-VL 基座模型"看图理解"比"看 world_state JSON"是更好还是更差
```

如果在这个阶段就发现基座模型根本不看图像、或者图像反而干扰了 JSON 格式输出，那说明需要 Phase 2 的图像微调。如果基座 VL 模型已经能看图说话，那就证明视觉方向成立。

### Phase 2 — 合成图像 + 多模态微调（1-2 周）

**目标**：用程序化生成的合成图像做端到端训练，验证整个多模态训练链路。

**关键决策：图像从哪来？**

| 方案 | 工具 | 优点 | 缺点 |
|:---|:---|:---|:---|
| **A: PIL/2D 合成** | `Pillow` + 简单图形 | 零依赖，生成快，可无限变体 | 和真实照片差距大，迁移性差 |
| **B: 3D 渲染** | `pyrender` / `Blender Python` | 接近真实视角，可控制光照和遮挡 | 需要 3D 模型资产（螺丝/齿轮/料盒） |
| **C: 物理仿真** | `Isaac Sim` / `MuJoCo` | 物理精确 + 可以顺便生成动作序列 | 重，学习成本高 |

**建议选 B（pyrender）**：轻量级 Python 渲染库，pip 可装，不需要 Blender 界面。用简单的几何体（圆柱=螺丝，球体=轴承，长方体=料盒）就能生成足够多样化的训练数据。

**训练侧改造**：

```
data_generator.py 改造:
  └─ generate_sample() 每生成一条文本样本
       └─ 同步调用 SceneRenderer.render(world_state) → 输出 train_xxx.jpg
       └─ sample["image_path"] = "data/images/train_xxx.jpg"

trainer.py 改造:
  └─ render_sample()  → 不再自己拼 ChatML，返回 messages 格式
  └─ preprocess()     → 用 processor(text=..., images=...) 替代 processor.tokenizer()
  └─ data_collator()  → 新增 pixel_values 和 image_grid_thw 的 batch 拼接
  └─ 视觉编码器      → 冻结（不参与 QLoRA），只训 LLM 侧的 LoRA adapter
```

**关键问题：QLoRA + 视觉编码器如何处理？**

Qwen3-VL 的视觉编码器（ViT）如果也被 4bit 量化，视觉特征质量会严重下降。正确做法：

```python
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    # 关键：排除视觉模块，不对 ViT 做 4bit 量化
    llm_int8_skip_modules=["visual"],  # 或使用 modules_to_not_convert
)
```

实际上 `bitsandbytes` 的 4bit 量化默认只作用于 Linear 层，Qwen3-VL 的 ViT 结构不同，通常不会被误量化。但需要在加载后验证 `visual` 相关参数仍然是 bf16。

**显存估算**：
- Base LLM (4bit): ~4-5GB
- ViT (bf16): ~1-2GB
- LoRA adapter: ~0.07GB
- 单张 512×512 图像的 pixel_values: ~0.5-1GB
- Batch=2 训练: ~12-15GB total → **5090 32G 够用**

### Phase 3 — 真实图像 + 混合训练（持续）

**目标**：用真实产线数据替代/补充合成数据，消除 sim-to-real gap。

- 在真实产线架摄像头，采集 `(图像, 工人话语, 标注 JSON)` 三元组
- 训练策略：先在合成数据上 warmup → 混合少量真实数据微调 → 逐步提高真实数据比例
- 这个阶段还需要处理：多视角、遮挡、光照变化、运动模糊

---

## 三、world_state 的渐进退场策略

当前 `world_state` JSON 是文本"作弊条"。有了视觉之后，应该逐步削弱它的作用：

```
Phase 1 (推理验证):   world_state 只作为补充上下文
                      提示词改为: "图片显示了当前场景。世界状态仅供参考，以图片为准。"

Phase 2 (合成训练):   world_state 退化
                      → 只提供容器位置（因为图像视角可能看不到所有容器）
                      → 物体信息（颜色/类型/缺陷）必须从图像中识别

Phase 3 (真实部署):   world_state 完全移除
                      → 模型只接收: 图像 + 工人话语
                      → 所有场景理解来自视觉
```

相应的训练提示词演进：

```
Phase 1: "请结合世界状态和图片判断..."
Phase 2: "图片显示了当前场景。世界状态可能不完整，以图片为准..."
Phase 3: "请根据图片中的场景理解工人的指令..."
```

---

## 四、8 类任务对视觉的依赖度

不是所有任务都需要高分辨率图像，按需分配：

| 视觉优先级 | 任务 | 图像要求 | 关键视觉特征 |
|:---|:---|:---|:---|
| **P0 必须有图** | 质检 | 高分辨率、微距 | 划痕、裂纹、变形、毛刺——纯视觉任务 |
| | 取料_放置 | 中分辨率、俯视 | 物体颜色/类型识别、位置确认 |
| **P1 图像有帮助** | 装配 | 中分辨率、侧面 | 零件对齐状态、扭矩扳手读数 |
| | 搬运 | 中分辨率、全局 | 源/目标位置确认、障碍物 |
| | 异常应对 | 可变、关键帧 | 卡料、掉落、异响（需音频？） |
| **P2 文本为主** | 换线 | 低分辨率 | 产线号显示面板 |
| | 状态查询 | 低分辨率 | 计数器/LED 显示屏 |
| | 协作等待 | 低分辨率 | 人体/手部检测、传感器指示灯 |

这意味着**第一阶段的合成图像生成应该优先覆盖 P0 和 P1 任务**。

---

## 五、总结：推荐的最小可行路径

```
Week 1:  Phase 1 推理验证
         ├─ 拍 10 张照片（手机即可）
         ├─ 改 inference.py predict_single 真正传图
         ├─ 对比 "有图" vs "纯文本 world_state" 的推理输出
         └─ 结论：视觉是否有增益？JSON 格式是否保持？

Week 2-3: Phase 2 合成图像渲染器
         ├─ pip install pyrender trimesh
         ├─ 写 SceneRenderer 类：根据 world_state 摆放几何体 → 渲染 PNG
         ├─ 改 data_generator：每条样本自动生成对应图像
         └─ 生成 448+104 张训练/测试图像

Week 3-4: Phase 2 多模态训练
         ├─ 改 trainer.py：messages → processor(images=...) → pixel_values
         ├─ 改 data_collator：支持 pixel_values + image_grid_thw batch
         ├─ 冻结 ViT，QLoRA 只训 LLM 部分
         └─ 跑通训练 → 评测 → 与纯文本基线对比
```

我把这个路线图写进 CLAUDE.md 吗？

---

## 👤 User

我们先把时间线理清楚：

当前（6月中旬-7月底）：第一阶段文本模型交付。 不改训练链路，不做图像。目标是用现有方案拿到88%+，按时交付给昆焱。你文档里把当前方案的局限诚实记录下来，作为下一阶段的技术债务。

交付完成后（8月）：启动第二阶段图文多模态升级。 你写的Phase 1推理验证→Phase 2合成图像训练→Phase 3真实图像混合训练，就按这个顺序推进。时间拉宽到4-5周，不赶工。

关于Phase 2的图像方案，我倾向你说的pyrender方案B——轻量、pip可装、不需要Blender界面。用几何体代替真实零件，足够验证多模态训练链路。

另外，world_state渐进退场策略很好。Phase 1验证时提示词改为‘以图片为准’，Phase 2训练时world_state只提供容器位置，Phase 3完全移除。这个演进逻辑清晰。

现在的任务不变： 继续按计划完成第一阶段文本模型的交付。你的技术路线图我们存档，作为8月第二阶段的执行方案。”



---

## 🤖 Claude

明白了。当前任务不变——第一阶段文本模型交付。我把视觉路线图存档进 CLAUDE.md 作为 8 月执行方案。

---

## 🤖 Claude

已存档。CLAUDE.md 现在的结构：

```
## ⚠️ Critical assessment: known leakage & limitations   ← 诚实记录当前技术债务
    Leakage #1-4 + Architectural gap
## Reality check: what the system actually does           ← 声称 vs 实际
    Minimum fixes (deferred to Phase 2)                   ← 标注为"延后到8月"

## Phase 2 roadmap: Vision-multimodal upgrade (August 2026)  ← 新增，8月执行方案
    Phase 2.1  推理先行验证 (Week 1)
    Phase 2.2  pyrender 合成图像 + 多模态训练 (Weeks 2-4)
       ├─ SceneRenderer 类设计
       ├─ 8 类任务视觉优先级 (P0/P1/P2)
       ├─ trainer.py 三处改造 (render_sample → preprocess → data_collator)
       ├─ QLoRA + ViT 冻结策略 + 显存估算
       └─ world_state 退化方案
    Phase 2.3  真实图像 + 混合训练 (Week 5+)
    world_state 三部曲: 完整 → 仅容器位置 → 完全移除
```

当前阶段的事情很清楚——文本模型交付，技术债务已记录，8 月按照 Phase 2.1 → 2.2 → 2.3 推进。

---

## 👤 User

你完全梳理一下输出给我，技术债务这一块

---

## 🤖 Claude

下面从**根因 → 现象 → 后果 → 处置**四个维度，把当前系统的技术债务完整梳理一遍。

---

## 技术债务全景

### 债务 #1：训练/测试共享模板池

**根因**：`data_generator.py` 的 `TASK_TEMPLATES` 是一个字典，`generate_dataset(seed=42)` 和 `generate_dataset(seed=1041)` 用的是同一个字典。唯一隔离是 utterance 字符串级别的去重。

```
训练时学到的是:  模板骨架 → JSON schema 的映射关系
测试时考的是:    同一个模板骨架，换了一套槽位值
```

**直接后果**：

- 基座模型（零微调）基线分数 80.5%，不是因为理解了工业指令，而是因为 Qwen3-VL 的文本抽取 + 查表替换能力足够覆盖模板变体
- 微调后的提升幅度（80.5% → 9x%）本质上是把模板匹配的精度从"还行"提到了"几乎完美"，不等于泛化能力提升
- 如果给一条不在模板库里的真实工人话语，模型表现会断崖式下降——但当前评测测不出这一点

**处置**：8 月手写 80-160 条 held-out 测试话语（每类任务 10-20 条），由真人撰写，包含碎片句、代词指代、自我纠正、方言表达，不与任何训练模板重复。这批数据只用于评测，不参与训练。

---

### 债务 #2：反向构建消灭了自然语言的模糊性

**根因**：`generate_sample()` 先调 `_build_expected_output()` 确定答案，再调 `_build_utterance_context()` 从答案反向提取模板变量，最后 `fill_template()` 造句。链条是：

```
随机数 → expected_output（答案）→ utterance_context → worker_utterance（题目）
```

**这意味着**：

| 真实工厂话语的特征 | 当前数据集的表现 |
|:---|:---|
| "那个"指代不明确，需要结合视线/手势 | "那个"永远对应 world_state 里唯一的同色物体 |
| 工人说一半改口："蓝色的...不对，红的" | 数据集不存在自我纠正 |
| 跳过已知信息："老规矩，放那边" | 每条话语都包含所有必要槽位值 |
| 夹杂无效信息："哎那个谁昨天说的..." | 数据集零噪声 |
| 依赖视觉上下文："电钻旁边那个" | 数据集零视觉依赖 |

**直接后果**：任务被退化成了**关键词提取 + JSON 查表填充**，不是真正的自然语言理解。模型不需要做任何推理、消歧、上下文追踪。

**处置**：8 月在 `data_generator.py` 中增加"噪声注入"模式——随机删除模板中的某个槽位（改用代词）、插入无关填充词、翻转语序。这个可以和 held-out 测试集同步做。

---

### 债务 #3：world_state 以结构化 JSON 明文喂给模型

**根因**：推理 prompt 是：

```python
f"世界状态: {json.dumps(sample['world_state'], ensure_ascii=False)}\n\n"
f"工人说: {sample['worker_utterance']}\n\n"
f"请输出 JSON:"
```

模型拿到的是预解析好的**答案索引表**——每个物体的 id、type、color、head、location 都以 JSON key-value 列出。

**直接后果**：

- 模型不需要从图像中识别物体颜色/类型，直接 CTL+F 搜索 JSON 文本即可
- 100% 的 JSON 格式合规率部分来自这个结构化输入的引导——模型知道有哪些字段、值的候选集是什么
- 真实部署时，没有一个传感器会输出格式完美的 JSON 世界状态。世界状态应该从视觉/传感器中**推断**，而不是直接拿到

**处置**：Phase 2.2 训练时 world_state 逐步退化——先砍掉物体的 type/color/head（这些改为必须从图像中识别），只保留容器位置（因为合成图像的固定视角可能看不到所有容器）。Phase 2.3 完全移除 world_state，模型只接收图像 + 话语。

---

### 债务 #4：must_match 字段太少，评分门槛过低

**根因**：每种任务只挑了 2-3 个字段做 must_match，其余是 optional（权重 0.5，错了或不输出惩罚一样）。

```
搬运: must_match = [action, target_location]
      模型只需要说出目的地，搬的是哪个物体（object）错了几乎不扣分

换线: must_match = [action, line_id]
      型号（model）错了不扣分

质检: must_match = [action, check_type, expected_answer]
      检查的是哪个物体（object）错了不扣分
```

**逐任务分析**：

| 任务 | must_match | 缺失的关键字段 | 安全风险 |
|:---|:---|:---|:---|
| 取料_放置 | action, color, container | **source**(物体id) | 抓错物体 |
| 装配 | action, type, base | **torque_nm**, **depth_mm** | 扭矩过大损坏零件，深度不对装配失败 |
| 换线 | action, line_id | model | 产线跑错型号 |
| 质检 | action, check_type, expected_answer | **object** | 检错物体，NG 品流出 |
| 搬运 | action, target_location | **object**, source | 搬错东西，从错的地方搬 |
| 异常应对 | action, urgency | **response_window_ms** | 响应太慢，事故扩大 |
| 状态查询 | action, query | — | 文本任务，查询类型包含在 must 里 |
| 协作等待 | action, resume_condition | — | 等待逻辑完整 |

**直接后果**：

- 得分公式的分母小，分子容易拿满分——对取料_放置，3个必须字段全对 + 所有 optional 不输出 = 3/5 = 0.60，已经过半
- 模型可以通过"只输出 must_match 字段 + 放弃 optional"的策略拿到 0.6-0.8 的分数，而这个策略完全绕过了物体 ID 等最难的部分
- 当前评分不反映机器人在真实场景中会不会做错事

**处置**：8 月重定义 eval_criteria。`source`/`object`/`force`/`params.*` 等安全关键字段全部升级为 must_match。新评分公式会导致基线分数大幅下降，但这才是诚实的基准线。

---

### 债务 #5：VL 模型当纯文本用，prompt 里撒谎

**根因**：基座选的是 Qwen3-**VL**-8B-Instruct（视觉语言模型），但：

- 训练/推理全链路不传图像
- `inference.py` 有 `image_path` 参数但所有调用方传 `None`
- `trainer.py` 的 `render_sample()` 是纯文本 ChatML，`preprocess()` 用 `processor.tokenizer()` 绕过了多模态 processor
- SYSTEM_PROMPT 却写着"必须严格依据工人说的话、世界状态**以及看到的图片**进行判断"

**直接后果**：

- 花了 VL 模型的显存和推理成本，只用到文本能力
- 如果 8 月换成 Qwen3-8B（纯文本），同参数量下推理更快、显存更小
- 技术方案和论文中声称"VL 多模态"，但目前没有任何多模态证据——这是评审硬伤

**处置**：Phase 2.1 推理验证时补上真正的图像输入。当前阶段在 prompt 里去掉了"图片"相关字眼（诚实化处理）。

---

### 债务汇总：从当前分数到诚实分数

当前基线 80.5% 是在四个泄漏叠加下的结果。如果逐一关闭：

```
当前基线:                           80.5%
  - 关闭债务#1 (held-out 测试集):   → 预计 40-60%
  - 关闭债务#2 (增加歧义+噪声):     → 预计 30-50%
  - 关闭债务#3 (移除 world_state):  → 预计 20-40%
  - 关闭债务#4 (收紧 must_match):   → 预计 15-35%
  - 关闭债务#5 (需要视觉理解):       → 只有 VL 模型能解决
─────────────────────────────────────────
诚实的基线:                         可能不到 20%
```

这不是说当前工作没有价值——模板槽位填充本身是合理的第一步，工程质量也很好。但 80.5% → 88% 这个数字在当前评测体系下的意义有限。真正衡量进度的方式是：**每关闭一项泄漏，分数掉多少，又通过模型改进追回来多少**。

---

## 👤 User

为什么这个QLoRa的速度这么快，几分钟这个demo都跑完了

---

## 🤖 Claude

让我把算力账算清楚。

---

## 🤖 Claude

核心答案就一句话：**整个训练只有 84 步、18 万 token、18M 可训参数——对一张 5090 来说连热身都不算。**

---

## 拆开看每一步的量

### 训练侧

```
448 条训练样本 × 3 epochs = 1,344 次前向/反向传播
batch=2, grad_accum=8 → 等效 batch=16
每 epoch = 448 ÷ 16 = 28 步
总计 = 28 × 3 = 84 步
```

84 步是什么概念？典型 LLM 微调的步数是 **500-5000 步**。这是训练脚本，不是训练——叫 few-step adaptation 更准确。

```
训练总 token 量: ~18 万
对比:
  LLaMA-Factory 典型微调: 100 万 - 1000 万 tokens
  Qwen 官方推荐微调:      ≥ 50 万 tokens
  当前灵脑:                18 万 tokens  ← 小了一个数量级以上
```

### 推理侧

```
测试集: 104 条
batch=4 → 26 次前向传播
基线 + 微调后 = 两轮推理 = 52 次 model.generate()
每次 generate 生成 ~50-100 tokens (JSON 很短)
贪心解码, 无 beam search, 无采样
```

### 参数侧

```
8,000,000,000  总参数 (8B)
       18,000,000  可训参数 (0.22%)
─────────────────
7,982,000,000  冻结不动

LoRA 只训 q_proj + k_proj + v_proj + o_proj 四个注意力矩阵的增量
每个增量矩阵 r=16, 参数量极小
反向传播不需要计算 99.78% 的参数的梯度
```

---

## 时间线还原

假设在一张 RTX 5090 32G 上跑 `python demo/run_demo.py --skip-train`：

| 阶段 | 耗时 | 说明 |
|:---|:---|:---|
| 加载数据 | ~1s | 读 448 + 104 条 JSONL |
| 加载基座模型 (bf16) | ~15-30s | 8B 参数, ~16GB 权重, 从磁盘读 + 转到 GPU |
| 基线推理 104 条 | ~30-60s | 26 批次, 每批 encode→forward→decode, ~1-2s/批 |
| 卸载模型 | ~1s | del model + cuda.empty_cache() |
| 重新加载模型 (4bit) | ~15-20s | 比 bf16 快, 权重只有 ~4-5GB |
| QLoRA 训练 84 步 | **~2-3 分钟** | 每步 ~1.5-2s (前向 4bit + 反向只算 LoRA 梯度) |
| 微调后推理 104 条 | ~30-60s | 同基线 |
| 评测 + 报告 | <1s | 纯 CPU 字符串匹配 |
| **总计** | **~5-7 分钟** | |

如果 `--skip-train`，更快：去掉训练和二次加载，**~2-3 分钟** 跑完。

---

## 为什么这么快？四个"缩水"叠加

```
              │  典型 LLM 微调  │  当前灵脑      │  差距
──────────────┼─────────────────┼────────────────┼────────
训练样本      │  5,000-100,000  │  448           │  10-200×
训练步数      │  500-5,000      │  84            │  6-60×
每样本 token  │  512-2048       │  ~300-400      │  ~2-5×
可训参数      │  100% (全量)    │  0.22% (LoRA)  │  450×
```

四个维度同时缩水，乘积效应让训练从"几小时"变成了"几分钟"。

---

## 这不是坏事，但要认识到代价

**快的代价是浅**：

- 84 步训练 ≈ 模型在每个模板骨架上平均只见过 **2-3 次**
- 模型学到的是"这句话骨架 → 那个 JSON schema"的浅层模式，不是深层语义理解
- 这就是为什么基线（零训练）已经 80.5%——因为 Qwen3-VL 的文本匹配能力本身就足够覆盖这个难度的任务

**反过来想**：如果数据集更大、更多样、更吵，训练时间会自然拉长到 30-60 分钟甚至几小时，但那时的分数才是真正反映系统能力的数字。当前的速度和分数，本质上是同一个原因的两面——任务太简单了。

---

## 👤 User

我想做一个pdf的技术文档，我直接把claude.md文档交给其他agent是不是就好了？你看看还有没有其他要补充的

---

## 🤖 Claude

CLAUDE.md 的内容量是够的，但它是一份**给 AI 看的操作手册**，不是**给人看的技术文档**。直接丢给 agent 会出几个问题：

---

## CLAUDE.md → 技术文档的差距

### 需要删掉的（内部内容，不适合对外）

| 章节 | 原因 |
|:---|:---|
| Critical assessment 全文 | "cheating"、"撒谎"——内部诚实可以，对外文档不合适 |
| Reality check 声称vs实际表 | 同上 |
| Legacy scripts 详细列表 | 对外文档只需要提"早期探索"，不需要逐个文件说明 |
| Module documentation 里的代码细节 | 技术文档要的是设计思路，不是函数签名 |
| Phase 2 roadmap | 内部规划，不进入当前版本文档 |

### 需要补充的（CLAUDE.md 里没有或不够）

1. **项目背景与问题定义**——为什么工厂需要这个系统？现有方案（人工翻译指令、PLC 编程）的痛点是什么。CLAUDE.md 只有一句"WAM 架构第一层"，没有展开。

2. **WAM 整体架构说明**——灵脑（指令理解）→ 灵境（世界模型安全预演）→ 执行，三者关系一句话带过，对外文档需要一张架构图（文字描述即可）和每层的职责边界。

3. **现有技术方案文档的引用/整合**——根目录有 `PRJ-01_灵脑_技术方案_v1.docx`，这份文档里应该有背景、架构、技术选型的论述。PDF 技术文档应该基于它更新，而不是从零写。

4. **实验数据**——`demo_report.json` 里有实际跑出来的分数（基线 80.49%），但没有写入 CLAUDE.md。技术文档需要：
   - 基线分数 + 微调后分数
   - 8 类任务各自的得分
   - JSON 解析成功率
   - 训练曲线（loss 下降）

5. **硬件/推理性能数据**——5090 上推理一条指令的延迟是多少 ms？吞吐量多少条/秒？这些是工业交付的关键指标，CLAUDE.md 完全没提。

6. **术语表**——WAM、QLoRA、ChatML、LoRA adapter、NF4 量化、must_match/optional，对外文档需要定义。

---

## 建议的做法

不要只丢 CLAUDE.md，打包三样东西给 agent：

```
输入 1: CLAUDE.md                       ← 技术事实的权威来源（代码架构、数据格式、公式）
输入 2: PRJ-01_灵脑_技术方案_v1.docx     ← 背景、架构论述、技术选型依据（需提取文字）
输入 3: demo/lingnao/outputs/demo_report.json  ← 实验数据
```

然后给 agent 明确的输出要求：

```
输出: PDF 技术文档，结构如下:
  1. 封面（项目名/版本/日期）
  2. 摘要
  3. 项目背景与问题定义
  4. WAM 系统架构
  5. 灵脑模块详细设计
     - 模型选型 (Qwen3-VL-8B + QLoRA)
     - 8 类任务定义与输出 schema
     - 数据生成方案
     - 训练方案 (ChatML, Loss Mask, 超参)
     - 推理方案
  6. 评测方法
  7. 实验结果
  8. 已知局限与后续规划
  9. 附录 (SYSTEM_PROMPT 全文, 超参表, 术语表)
```

要我先把这三样东西准备好，然后调度 agent 生成 PDF 吗？

---

