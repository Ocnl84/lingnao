"""
灵脑 — 训练脚本
================

技术方案第八节完整实现：QLoRA 4bit 微调 Qwen3-VL-8B-Instruct。

硬件要求: RTX 5090 (32G) 或 A100-40G
数据格式: JSONL，每条样本包含 worker_utterance + world_state + expected_output
输出: LoRA 适配器 (~70MB)，保存在 outputs/lora_out/
"""

import json
import os
import sys
from typing import Dict, List, Optional

import torch
from datasets import Dataset
from transformers import (
    Qwen3VLForConditionalGeneration,
    AutoProcessor,
    TrainingArguments,
    Trainer,
    BitsAndBytesConfig,
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    PeftModel,
)

try:
    from .config import (
        MODEL_PATH, TRAIN_FILE, OUTPUT_DIR, SYSTEM_PROMPT,
        LoRAConfig as LoRAConfigData,
        TrainingConfig as TrainingConfigData,
        VALID_ACTIONS,
    )
except ImportError:
    from config import (
        MODEL_PATH, TRAIN_FILE, OUTPUT_DIR, SYSTEM_PROMPT,
        LoRAConfig as LoRAConfigData,
        TrainingConfig as TrainingConfigData,
        VALID_ACTIONS,
    )


# ═══════════════════════════════════════════════════════════
# 数据加载与渲染
# ═══════════════════════════════════════════════════════════

def load_jsonl(path: str) -> List[Dict]:
    """加载 JSONL 数据集"""
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def render_sample(sample: Dict) -> str:
    """
    将一条样本渲染成 ChatML 格式的字符串。

    与技术方案 4.3 一致：
      <|im_start|>system ... <|im_end|>
      <|im_start|>user ... <|im_end|>
      <|im_start|>assistant ... <|im_end|>
    """
    # 🖼️ 图像占位符：当训练数据包含图像时，需在 user_text 前插入 <|vision_start|><|image_pad|><|vision_end|>
    # 并在 preprocess 阶段将图像张量传给 processor。目前训练为纯文本模式。
    user_text = (
        f"工人说: {sample['worker_utterance']}\n\n"
        f"请输出 JSON:"
    )
    assistant_text = json.dumps(sample["expected_output"], ensure_ascii=False)

    chat = (
        f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
        f"<|im_start|>user\n{user_text}<|im_end|>\n"
        f"<|im_start|>assistant\n{assistant_text}<|im_end|>"
    )
    return chat


# ═══════════════════════════════════════════════════════════
# 核心训练函数
# ═══════════════════════════════════════════════════════════

def train(
    train_file: str = TRAIN_FILE,
    model_path: str = MODEL_PATH,
    output_dir: str = os.path.join(OUTPUT_DIR, "lora_out"),
    lora_config: Optional[LoRAConfigData] = None,
    training_config: Optional[TrainingConfigData] = None,
) -> str:
    """
    QLoRA 微调主函数。

    Args:
        train_file: 训练数据 JSONL 路径
        model_path: 基座模型路径
        output_dir: LoRA 输出目录
        lora_config: LoRA 配置
        training_config: 训练超参

    Returns:
        最终 LoRA 适配器保存路径
    """
    if lora_config is None:
        lora_config = LoRAConfigData()
    if training_config is None:
        training_config = TrainingConfigData()

    # ── 1. 加载训练数据 ──
    print(f"📂 加载训练数据: {train_file}")
    raw_samples = load_jsonl(train_file)
    print(f"   共 {len(raw_samples)} 条样本")
    print(f"   任务类型分布: {_count_task_types(raw_samples)}")

    # ── 2. 4bit 量化配置 ──
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    # ── 3. 加载基座模型（4bit 量化） ──
    print(f"🤖 加载基座模型: {model_path}")
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_path,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16,
    )

    # 准备 4bit 模型用于 LoRA 训练
    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=training_config.gradient_checkpointing,
    )

    # ── 4. LoRA 配置 ──
    peft_config = LoraConfig(
        r=lora_config.r,
        lora_alpha=lora_config.lora_alpha,
        target_modules=lora_config.target_modules,
        lora_dropout=lora_config.lora_dropout,
        bias=lora_config.bias,
        task_type=lora_config.task_type,
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # ── 5. 加载 processor ──
    processor = AutoProcessor.from_pretrained(model_path)

    # ── 6. 预处理 ──
    print("🔧 预处理数据...")

    def preprocess(sample: Dict) -> Dict:
        """渲染 → tokenize → mask user 部分"""
        chat = render_sample(sample)
        # 用 tokenizer 直接 tokenize 预渲染的 ChatML 文本，避免
        # Qwen3-VL processor 引入多模态维度导致 collator 报错
        encoded = processor.tokenizer(
            chat,
            return_tensors=None,
            padding=False,
            truncation=True,
            max_length=training_config.max_seq_length,
        )
        input_ids = encoded["input_ids"]

        # 找 assistant 起始位置（只对 assistant 部分算 loss）
        assistant_marker = processor.tokenizer.encode(
            "<|im_start|>assistant\n", add_special_tokens=False
        )
        marker_len = len(assistant_marker)
        labels = [-100] * len(input_ids)

        for i in range(len(input_ids) - marker_len + 1):
            if input_ids[i:i + marker_len] == assistant_marker:
                start = i + marker_len
                for j in range(start, len(input_ids)):
                    labels[j] = input_ids[j]
                break

        return {
            "input_ids": input_ids,
            "attention_mask": encoded["attention_mask"],
            "labels": labels,
        }

    processed = [preprocess(s) for s in raw_samples]
    dataset = Dataset.from_list(processed)
    print(f"   预处理完成，{len(dataset)} 条")

    # ── 7. Data Collator ──
    def data_collator(features: List[Dict]) -> Dict:
        """Padding 到同长，兼容 tokenizer 返回的嵌套 list"""
        # 展平可能的嵌套结构
        clean_features = []
        for f in features:
            cf = {}
            for key in ("input_ids", "attention_mask", "labels"):
                val = f.get(key, [])
                # tokenizer 可能返回嵌套 list，展平
                while isinstance(val, list) and len(val) == 1 and isinstance(val[0], list):
                    val = val[0]
                cf[key] = val
            clean_features.append(cf)

        max_len = max(len(f["input_ids"]) for f in clean_features)
        pad_token_id = processor.tokenizer.pad_token_id or 0

        input_ids, attention_mask, labels = [], [], []
        for f in clean_features:
            pad_len = max_len - len(f["input_ids"])
            input_ids.append(f["input_ids"] + [pad_token_id] * pad_len)
            attention_mask.append(f["attention_mask"] + [0] * pad_len)
            labels.append(f["labels"] + [-100] * pad_len)

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }

    # ── 8. 训练参数 ──
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=training_config.num_train_epochs,
        per_device_train_batch_size=training_config.per_device_train_batch_size,
        gradient_accumulation_steps=training_config.gradient_accumulation_steps,
        learning_rate=training_config.learning_rate,
        warmup_ratio=training_config.warmup_ratio,
        weight_decay=training_config.weight_decay,
        lr_scheduler_type=training_config.lr_scheduler_type,
        bf16=training_config.bf16,
        logging_steps=training_config.logging_steps,
        save_strategy=training_config.save_strategy,
        save_total_limit=training_config.save_total_limit,
        optim=training_config.optim,
        gradient_checkpointing=training_config.gradient_checkpointing,
        report_to="none",
        dataloader_num_workers=2,
    )

    # ── 9. 训练 ──
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=data_collator,
    )

    print("🚀 开始训练...")
    print(f"   样本数: {len(raw_samples)}")
    print(f"   Epochs: {training_config.num_train_epochs}")
    print(f"   Batch size (等效): {training_config.per_device_train_batch_size * training_config.gradient_accumulation_steps}")
    print(f"   Learning rate: {training_config.learning_rate}")

    trainer.train()

    # ── 10. 保存 LoRA ──
    final_dir = os.path.join(output_dir, "final")
    print(f"💾 保存 LoRA 适配器 → {final_dir}")
    model.save_pretrained(final_dir)
    processor.save_pretrained(final_dir)

    # 打印模型大小
    adapter_path = os.path.join(final_dir, "adapter_model.safetensors")
    if os.path.exists(adapter_path):
        size_mb = os.path.getsize(adapter_path) / (1024 * 1024)
        print(f"   LoRA 适配器大小: {size_mb:.1f} MB")

    print("✅ 训练完成!")
    return final_dir


def _count_task_types(samples: List[Dict]) -> Dict[str, int]:
    """统计任务类型分布"""
    from collections import Counter
    return dict(Counter(s.get("task_type", "unknown") for s in samples))


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PRJ-01 灵脑 — QLoRA 微调")
    parser.add_argument("--train-file", default=TRAIN_FILE)
    parser.add_argument("--model-path", default=MODEL_PATH)
    parser.add_argument("--output-dir", default=os.path.join(OUTPUT_DIR, "lora_out"))
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=2)
    args = parser.parse_args()

    tc = TrainingConfigData(
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size,
    )

    train(
        train_file=args.train_file,
        model_path=args.model_path,
        output_dir=args.output_dir,
        training_config=tc,
    )
