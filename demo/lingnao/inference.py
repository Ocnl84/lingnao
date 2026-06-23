"""
灵脑 — 推理模块
================

技术方案第九节：加载 LoRA 适配器进行推理。

支持：
  - 动态加载 LoRA（不合并权重）
  - 批量推理
  - 贪心解码（确定性输出，用于评测）
"""

import json
import os
import sys
import argparse
from typing import Dict, List, Optional

import torch
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
from peft import PeftModel

try:
    from .config import MODEL_PATH, SYSTEM_PROMPT, TEST_FILE, OUTPUT_DIR
    from .eval import safe_parse_json
except ImportError:
    from config import MODEL_PATH, SYSTEM_PROMPT, TEST_FILE, OUTPUT_DIR
    from eval import safe_parse_json


def load_model_with_lora(
    base_path: str = MODEL_PATH,
    lora_path: Optional[str] = None,
    device_map: str = "auto",
):
    """
    加载模型（可选加载 LoRA 适配器）。

    Args:
        base_path: 基座模型路径
        lora_path: LoRA 适配器路径（None 则只用基座）
        device_map: 设备分配策略

    Returns:
        (model, processor)
    """
    print(f"🤖 加载基座模型: {base_path}")
    base = Qwen3VLForConditionalGeneration.from_pretrained(
        base_path,
        torch_dtype=torch.bfloat16,
        device_map=device_map,
    )
    processor = AutoProcessor.from_pretrained(base_path)
    # Qwen3-VL 是 decoder-only 架构，必须左 padding
    processor.tokenizer.padding_side = "left"

    if lora_path and os.path.exists(lora_path):
        print(f"🔌 加载 LoRA 适配器: {lora_path}")
        model = PeftModel.from_pretrained(base, lora_path)
    else:
        print("   (未加载 LoRA，使用基座模型)")
        model = base

    model.eval()
    return model, processor


def predict_single(
    model,
    processor,
    sample: Dict,
    max_new_tokens: int = 512,
    do_sample: bool = False,
    temperature: float = 1.0,
    image_path: Optional[str] = None,
) -> Dict:
    """
    对单条样本推理。

    Args:
        sample: {"id": ..., "worker_utterance": ..., "world_state": ...}
        image_path: 🖼️ 图像占位符 — 可选，传入当前场景的图片路径

    Returns:
        {"id": ..., "raw_output": ..., "parsed": ...}
    """
    user_text = (
        f"工人说: {sample.get('worker_utterance', '')}\n\n"
        f"请输出 JSON:"
    )

    # 🖼️ 图像占位符：当有图像输入时传入 image_path，图像将与文本一起送入 Qwen3-VL
    user_content: list = []
    if image_path:
        user_content.append({"type": "image", "image": image_path})
    user_content.append({"type": "text", "text": user_text})

    messages = [
        {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
        {"role": "user", "content": user_content},
    ]

    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    # 🖼️ 图像占位符：有图像时需将 PIL Image 一并传入 processor
    if image_path:
        from PIL import Image as PILImage
        image = PILImage.open(image_path).convert("RGB")
        inputs = processor(text=[text], images=[image], return_tensors="pt", padding=True).to(model.device)
    else:
        inputs = processor(text=[text], return_tensors="pt", padding=True).to(model.device)

    with torch.no_grad():
        generated = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            temperature=temperature,
        )

    raw_output = processor.batch_decode(
        generated[:, inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )[0]

    parsed = safe_parse_json(raw_output)

    return {
        "id": sample.get("id", ""),
        "raw_output": raw_output,
        "parsed": parsed,
    }


def predict_batch(
    model,
    processor,
    samples: List[Dict],
    batch_size: int = 4,
    max_new_tokens: int = 512,
    image_paths: Optional[List[Optional[str]]] = None,
) -> List[Dict]:
    """
    批量推理。

    Args:
        samples: 样本列表
        batch_size: 批次大小
        image_paths: 🖼️ 图像占位符 — 可选，与 samples 等长的图片路径列表（无图像的样本填 None）

    Returns:
        预测结果列表
    """
    results = []
    total = len(samples)

    for i in range(0, total, batch_size):
        batch = samples[i:i + batch_size]
        batch_texts = []
        batch_images = []  # 🖼️ 收集本批次需要传入的图像

        for j, sample in enumerate(batch):
            user_text = (
                f"工人说: {sample.get('worker_utterance', '')}\n\n请输出 JSON:"
            )

            # 🖼️ 图像占位符：当有图像时加入 content，否则纯文本
            user_content: list = []
            img_path = image_paths[i + j] if image_paths and i + j < len(image_paths) else None
            if img_path:
                user_content.append({"type": "image", "image": img_path})
            user_content.append({"type": "text", "text": user_text})

            messages = [
                {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
                {"role": "user", "content": user_content},
            ]
            text = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            batch_texts.append(text)
            batch_images.append(img_path)  # None or str

        # 🖼️ 图像占位符：加载本批次有效图像
        if any(batch_images):
            from PIL import Image as PILImage
            images = []
            for p in batch_images:
                images.append(PILImage.open(p).convert("RGB") if p else None)
            inputs = processor(text=batch_texts, images=images, return_tensors="pt", padding=True, truncation=True).to(model.device)
        else:
            inputs = processor(text=batch_texts, return_tensors="pt", padding=True, truncation=True).to(model.device)

        with torch.no_grad():
            generated = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=1.0,
            )

        outputs = processor.batch_decode(
            generated[:, inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )

        for j, sample in enumerate(batch):
            parsed = safe_parse_json(outputs[j])
            results.append({
                "id": sample.get("id", ""),
                "raw_output": outputs[j],
                "parsed": parsed,
            })

        print(f"  推理进度: {min(i + batch_size, total)}/{total}")

    return results


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PRJ-01 灵脑 — 推理")
    parser.add_argument("--base", default=MODEL_PATH, help="基座模型路径")
    parser.add_argument("--lora", default=None, help="LoRA 适配器路径（可选）")
    parser.add_argument("--test", default=TEST_FILE, help="测试集 JSONL 路径")
    parser.add_argument("--output", default=os.path.join(OUTPUT_DIR, "preds.jsonl"), help="预测输出路径")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    args = parser.parse_args()

    model, processor = load_model_with_lora(
        base_path=args.base,
        lora_path=args.lora,
    )

    if args.interactive:
        print("\n🔧 灵脑 交互模式")
        print("   输入工人指令，Ctrl+C 退出\n")
        try:
            while True:
                utterance = input("工人说: ").strip()
                if not utterance:
                    continue
                sample = {
                    "id": "interactive",
                    "worker_utterance": utterance,
                    "world_state": {
                        "objects": [
                            {"id": "obj_001", "type": "螺丝", "color": "蓝色", "head": "十字", "location": "箱子A"},
                        ],
                        "containers": [
                            {"id": "box_001", "position": "左一", "capacity": 10},
                            {"id": "box_002", "position": "左二", "capacity": 10},
                        ],
                    },
                }
                result = predict_single(model, processor, sample)
                print(f"灵脑: {json.dumps(result['parsed'], ensure_ascii=False, indent=2) if result['parsed'] else result['raw_output']}\n")
        except KeyboardInterrupt:
            print("\n👋 退出")
    else:
        # 批量推理模式
        with open(args.test, encoding="utf-8") as f:
            test_samples = [json.loads(line) for line in f if line.strip()]

        print(f"📊 推理 {len(test_samples)} 条测试样本...")
        preds = predict_batch(model, processor, test_samples, batch_size=args.batch_size)

        with open(args.output, "w", encoding="utf-8") as f:
            for p in preds:
                # 把 parsed 转成可读 JSON
                out = {k: v for k, v in p.items()}
                f.write(json.dumps(out, ensure_ascii=False, default=str) + "\n")

        print(f"✅ 预测已保存 → {args.output}")

        # 简单统计
        parsed_ok = sum(1 for p in preds if p["parsed"] is not None)
        print(f"   JSON 解析成功率: {parsed_ok}/{len(preds)} ({parsed_ok/len(preds)*100:.1f}%)")
