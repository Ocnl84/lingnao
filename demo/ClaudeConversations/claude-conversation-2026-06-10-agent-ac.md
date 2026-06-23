# Claude Conversation Log

Session ID: agent-acbd854ea390003a9
Date: 2026-06-10 08:00:07

---

## 👤 User

Explore the /root/Brain/demo directory thoroughly. I need to understand:
1. The overall project structure
2. Where Qwen model inference/prediction happens
3. Where prompts for Qwen are defined
4. How the current input pipeline works (especially whether images are handled)
5. The data format in lingnao/data/train_v1.jsonl (just a few lines to understand the schema)

Focus on finding files related to: Qwen, model inference, prompts, image handling. Be very thorough.

---

## 🤖 Claude

I'll explore the project structure thoroughly, starting with multiple parallel searches.

---

## 🤖 Claude

Good. Now let me read all the main source files in parallel.

---

## 🤖 Claude

Now let me also check the remaining files for completeness.

---

## 🤖 Claude

Let me also quickly check the test file and verify the test_v1.jsonl format.

---

## 🤖 Claude

Here is a thorough report of my findings.

---

## Complete Project Analysis: /root/Brain/demo

### 1. Overall Project Structure

This is **PRJ-01 "Lingnao" (灵脑)** -- an industrial robot instruction fine-tuning demo. It is the first layer of a WAM (World-Action Model) architecture that converts worker natural language instructions into structured JSON commands.

```
/root/Brain/demo/
├── run_demo.py                  # Main entry point
├── test_evaluator.py            # Unit tests for evaluator
├── .claude/
│   └── settings.local.json      # Local Claude permissions
└── lingnao/
    ├── __init__.py              # Package docstring
    ├── config.py                # Centralized config (paths, hyperparams, prompts)
    ├── data_generator.py        # Training/test data generation (8 task types)
    ├── evaluator.py             # Strict field-level JSON evaluation
    ├── trainer.py               # QLoRA fine-tuning script
    ├── inference.py             # Inference (load LoRA, batch/interactive)
    ├── data/
    │   ├── train_v1.jsonl       # Training set (48 samples)
    │   └── test_v1.jsonl        # Test set (16 samples)
    └── outputs/
        ├── demo_report.json     # Latest run report
        └── lora_out/            # LoRA adapter checkpoints
            ├── checkpoint-6/
            ├── checkpoint-9/
            └── final/
```

The demo pipeline runs 5 steps: data generation, baseline evaluation (no LoRA), QLoRA training, fine-tuned evaluation, and a comparison report.

---

### 2. Where Qwen Model Inference/Prediction Happens

All Qwen model loading and inference lives in **two files**:

**`/root/Brain/demo/lingnao/inference.py`**
- `load_model_with_lora()` (line 28-62): Loads `Qwen3VLForConditionalGeneration` from `transformers`, optionally merges a LoRA adapter via `PeftModel.from_pretrained()`. Returns `(model, processor)`.
- `predict_single()` (line 65-117): Single-sample inference. Builds a ChatML message list, applies the chat template, tokenizes (text-only), calls `model.generate()`, decodes, and parses JSON from the output.
- `predict_batch()` (line 120-188): Batch inference. Same flow as `predict_single` but batched with padding. Uses greedy decoding (`do_sample=False`).
- Also has its own CLI entrypoint (line 194-253) for standalone use.

**`/root/Brain/demo/run_demo.py`**
- Line 99-104: Calls `load_model_with_lora(base_path=MODEL_PATH, lora_path=None)` then `predict_batch()` for baseline.
- Line 151-156: Calls `load_model_with_lora(base_path=MODEL_PATH, lora_path=lora_path)` then `predict_batch()` for fine-tuned eval.
- Line 223-255: `run_interactive()` -- loads model, takes user input, calls `predict_single()`.

**Model path** (configured in `/root/Brain/demo/lingnao/config.py` line 18-21):
```
/root/autodl-tmp/model_cache/qwen/Qwen3-VL-8B-Instruct
```
Configurable via env var `LINGNAO_MODEL_PATH`.

**Training** also uses `Qwen3VLForConditionalGeneration` (in `/root/Brain/demo/lingnao/trainer.py` line 129).

---

### 3. Where Prompts for Qwen Are Defined

The single system prompt is defined in **`/root/Brain/demo/lingnao/config.py`**, lines 86-118, as the constant `SYSTEM_PROMPT`. It is a multi-line string that describes the task (industrial robot instruction understanding) and defines the output JSON schema for all 8 action types:

- 取料_放置 (Pick & Place)
- 装配 (Assembly)
- 换线 (Line change)
- 质检 (Quality inspection)
- 搬运 (Transport)
- 异常应对 (Anomaly response)
- 状态查询 (Status query)
- 协作等待 (Collaboration wait)

The prompt is used in:
- **Inference**: `/root/Brain/demo/lingnao/inference.py` line 89 and 150 -- passed as the system message content in the ChatML format.
- **Training**: `/root/Brain/demo/lingnao/trainer.py` line 77 -- embedded directly into the pre-rendered ChatML string in `render_sample()`.

The user message in both training and inference consists of:
```
"世界状态: <world_state JSON>\n\n工人说: <utterance>\n\n请输出 JSON:"
```

---

### 4. How the Current Input Pipeline Works (Especially Regarding Images)

**The current pipeline is text-only. Images are NOT used in any way.**

Here is the detailed evidence:

- In `predict_single()` (inference.py lines 82-96), the user message content is constructed as:
  ```python
  messages = [
      {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
      {"role": "user", "content": [{"type": "text", "text": user_text}]},
  ]
  ```
  The content list only contains `{"type": "text", ...}` -- no `{"type": "image", ...}` elements.

- In `predict_batch()` (inference.py lines 144-153), it is the same: only text content.

- In `trainer.py` `render_sample()` (line 60-81), the training data is rendered as a plain ChatML string -- no image content.

- In `trainer.py` `preprocess()` (line 160-192), the code explicitly notes (line 163-165):
  ```python
  # Qwen3-VL processor 引入多模态维度导致 collator 报错
  encoded = processor.tokenizer(...)
  ```
  This means they deliberately use `processor.tokenizer` (pure text tokenizer) instead of `processor()` to avoid multi-modal dimensions that would cause the data collator to fail.

- **The `world_state` field in the data is JSON text**, containing object properties like `type`, `color`, `head`, `material`, `location`. There are no image URLs, no image paths, no base64-encoded images.

- The tokenizer config at `/root/Brain/demo/lingnao/outputs/lora_out/final/tokenizer_config.json` contains vision-related tokens (`<|vision_start|>`, `<|vision_end|>`, `<|vision_pad|>`, `<|image_pad|>`) and the processor config at `processor_config.json` contains `Qwen2VLImageProcessor` and `Qwen3VLVideoProcessor`, but these are artifacts of the Qwen3-VL base model -- no code in the project actually uses the vision capabilities.

- **No image files** (png, jpg, bmp, gif, webp) exist anywhere in the project directory.

The model `Qwen3-VL-8B-Instruct` is a vision-language model, but this project only uses its text/chat capabilities. The dataset contains textual descriptions of world state (objects and their visual attributes like color, head type, size) rather than actual images.

---

### 5. Data Format in `train_v1.jsonl`

The file is at `/root/Brain/demo/lingnao/data/train_v1.jsonl` (48 lines, one JSON object per line). Each sample has this schema:

```json
{
  "id": "train_取料_放置_001",
  "task_type": "取料_放置",
  "worker_utterance": "把那个黑色内六角的螺丝放到左一里",
  "world_state": {
    "objects": [
      {"id": "obj_350", "type": "螺丝", "color": "黑色", "head": "内六角", "material": "不锈钢", "location": "箱子B"}
    ],
    "containers": [
      {"id": "box_704", "type": "料盒", "position": "左一", "capacity": 18}
    ]
  },
  "expected_output": {
    "action": "取料_放置",
    "object_filter": {"color": "黑色", "head": "内六角"},
    "source": "obj_350",
    "target": {"container": "box_704"},
    "force": "轻",
    "urgency": "常规"
  },
  "eval_criteria": {
    "must_match": ["action", "object_filter.color", "target.container"],
    "optional": ["object_filter", "source", "target", "force"],
    "match_type": "exact_field_match"
  }
}
```

Key fields:
- **id**: Unique sample identifier with task type prefix
- **task_type**: One of 8 types (取料_放置, 装配, 换线, 质检, 搬运, 异常应对, 状态查询, 协作等待)
- **worker_utterance**: The worker's natural language instruction (Chinese)
- **world_state.objects**: Array of objects with id, type, and visual/spec attributes (color, head, material, size, teeth, etc.) plus location
- **world_state.containers**: Array of containers with id, type, position, capacity
- **expected_output**: The ground-truth structured JSON the model should produce
- **eval_criteria.must_match**: Fields that must match exactly (errors deduct full points)
- **eval_criteria.optional**: Fields that add partial credit if present and correct

The test file (`test_v1.jsonl`) has the same schema with 16 samples.

---

### Summary of Key Files

| File | Purpose |
|------|---------|
| `/root/Brain/demo/run_demo.py` | Main entry, orchestrates 5-step pipeline |
| `/root/Brain/demo/lingnao/config.py` | All paths, hyperparams, `SYSTEM_PROMPT` constant |
| `/root/Brain/demo/lingnao/inference.py` | Model loading (`Qwen3VLForConditionalGeneration`), `predict_single()`, `predict_batch()` |
| `/root/Brain/demo/lingnao/trainer.py` | QLoRA training with `Qwen3VLForConditionalGeneration` |
| `/root/Brain/demo/lingnao/evaluator.py` | `safe_parse_json()`, `score_sample()`, `evaluate_dataset()`, `print_report()` |
| `/root/Brain/demo/lingnao/data_generator.py` | Template-based dataset generation for 8 task types |
| `/root/Brain/demo/test_evaluator.py` | Unit tests for the evaluator module |
| `/root/Brain/demo/lingnao/data/train_v1.jsonl` | Training data (48 samples) |
| `/root/Brain/demo/lingnao/data/test_v1.jsonl` | Test data (16 samples) |
| `/root/Brain/demo/lingnao/outputs/demo_report.json` | Latest run results (baseline: 82.05%, fine-tuned: 90.62%) |

**Critical observation**: The project uses `Qwen3-VL-8B-Instruct` (a vision-language model) but only in text mode. No images are loaded, processed, or passed to the model. The input pipeline constructs messages with only `{"type": "text"}` content blocks. The processor is used only for its tokenizer. To add image support, you would need to modify the message construction in `inference.py` (`predict_single` and `predict_batch`) and the training data rendering in `trainer.py` (`render_sample` and `preprocess`), plus add image fields to the dataset schema.

---

