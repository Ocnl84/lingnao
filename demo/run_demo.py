#!/usr/bin/env python3
"""
====================================================================
 PRJ-01 灵脑 — 工业指令微调 Demo
====================================================================

WAM 架构第一层完整演示：
  数据集加载 → 基线测试 → 微调训练 → 推理评测 → 结果报告

用法:
  python run_demo.py                     # 读取 PRJ 数据集，跑推理+训练
  python run_demo.py --skip-train        # 跳过训练，只用基线
  python run_demo.py --interactive       # 交互模式

环境:
  pip install transformers peft bitsandbytes datasets accelerate
====================================================================
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Optional

# 将 lingnao 包加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lingnao.config import (
    OUTPUT_DIR, TRAIN_FILE, TEST_FILE,
    VALID_ACTIONS, PASS_THRESHOLD, MODEL_PATH,
)
from lingnao.eval import score_sample, evaluate_dataset, print_report


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════

def step_header(title: str):
    """打印步骤标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def load_jsonl(path: str) -> list:
    """加载 JSONL 数据集"""
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def load_datasets(train_file: str, test_file: str):
    """
    加载 PRJ 数据集。

    Args:
        train_file: 训练集路径
        test_file: 测试集路径

    Returns:
        (train_samples, test_samples)
    """
    step_header("Step 1/5: 加载数据集")

    if not os.path.exists(train_file):
        sys.exit(f"❌ 训练集不存在: {train_file}")
    if not os.path.exists(test_file):
        sys.exit(f"❌ 测试集不存在: {test_file}")

    train_samples = load_jsonl(train_file)
    print(f"  📂 训练集: {os.path.basename(train_file)} → {len(train_samples)} 条")

    test_samples = load_jsonl(test_file)
    print(f"  📂 测试集: {os.path.basename(test_file)} → {len(test_samples)} 条")

    return train_samples, test_samples


def run_full_demo(skip_train: bool = True):
    """
    运行完整 Demo 流程。

    流程:
      Step 1: 加载 PRJ 数据集
      Step 2: 基线测试（基座模型，无 LoRA）
      Step 3: QLoRA 微调训练
      Step 4: 微调后推理 + 评测
      Step 5: 生成对比报告

    Args:
        skip_train: 跳过训练步骤
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "mode": "gpu",
        "steps": {},
    }

    # ════════════════════════════════════════════════════════
    # Step 1: 加载/生成数据集
    # ════════════════════════════════════════════════════════
    train_samples, test_samples = load_datasets(TRAIN_FILE, TEST_FILE)

    results["steps"]["data_load"] = {
        "train_count": len(train_samples),
        "test_count": len(test_samples),
    }

    # 打印样本分布
    from collections import Counter
    train_dist = Counter(s["task_type"] for s in train_samples)
    print(f"\n  训练集分布:")
    for task, count in train_dist.items():
        print(f"    {task}: {count} 条")
    print(f"  测试集: {len(test_samples)} 条")

    # ════════════════════════════════════════════════════════
    # Step 2: 基线测试
    # ════════════════════════════════════════════════════════
    step_header("Step 2/5: 基线测试（微调前）")

    from lingnao.inference import load_model_with_lora, predict_batch

    print("  🖥️  加载基座模型（无 LoRA）...")
    model, processor = load_model_with_lora(
        base_path=MODEL_PATH, lora_path=None
    )
    print(f"  🚀 推理 {len(test_samples)} 条测试样本...")
    baseline_preds = predict_batch(model, processor, test_samples, batch_size=4)

    # 释放基座模型显存，为训练腾空间
    del model
    import torch
    torch.cuda.empty_cache()

    baseline_result = evaluate_dataset(baseline_preds, test_samples)
    print_report(baseline_result)
    results["steps"]["baseline"] = {
        "avg_score": baseline_result["avg_score"],
        "format_pass_rate": baseline_result["format_pass_rate"],
        "passed": baseline_result["passed"],
    }

    # ════════════════════════════════════════════════════════
    # Step 3: 微调训练
    # ════════════════════════════════════════════════════════
    step_header("Step 3/5: QLoRA 微调训练")

    lora_path: Optional[str] = None

    if skip_train:
        print("  ⏭️  跳过训练（--skip-train）")
        results["steps"]["training"] = {"status": "skipped"}
    else:
        from lingnao.trainer import train

        print("  🖥️  开始 QLoRA 训练...")
        try:
            lora_path = train(train_file=TRAIN_FILE)
            results["steps"]["training"] = {
                "status": "completed",
                "lora_path": lora_path,
            }
        except Exception as e:
            print(f"  ⚠️  训练失败: {e}")
            results["steps"]["training"] = {"status": "failed", "error": str(e)}

    # ════════════════════════════════════════════════════════
    # Step 4: 微调后推理 + 评测
    # ════════════════════════════════════════════════════════
    step_header("Step 4/5: 微调后推理评测")

    if lora_path and os.path.exists(lora_path):
        from lingnao.inference import load_model_with_lora, predict_batch

        print("  🖥️  加载微调后模型...")
        model, processor = load_model_with_lora(
            base_path=MODEL_PATH, lora_path=lora_path
        )
        print(f"  🚀 推理 {len(test_samples)} 条测试样本...")
        tuned_preds = predict_batch(model, processor, test_samples, batch_size=4)
    else:
        # 无 LoRA 可用（跳过训练或训练失败），复用基线结果
        print("  ⚠️  无 LoRA 适配器，无法进行微调后推理")
        tuned_preds = baseline_preds

    tuned_result = evaluate_dataset(tuned_preds, test_samples)
    print_report(tuned_result)
    results["steps"]["tuned"] = {
        "avg_score": tuned_result["avg_score"],
        "format_pass_rate": tuned_result["format_pass_rate"],
        "passed": tuned_result["passed"],
    }

    # ════════════════════════════════════════════════════════
    # Step 5: 对比报告
    # ════════════════════════════════════════════════════════
    step_header("Step 5/5: 最终报告")

    baseline_score = results["steps"]["baseline"]["avg_score"]
    tuned_score = results["steps"]["tuned"]["avg_score"]
    improvement = tuned_score - baseline_score

    print(f"""
  ┌──────────────────────────────────────────────────────┐
  │          PRJ-01 灵脑 — Demo 验证报告                 │
  ├──────────────────────────────────────────────────────┤
  │  数据集:       训练 {results['steps']['data_load']['train_count']} 条 / 测试 {results['steps']['data_load']['test_count']} 条
  │  任务类型:     {len(VALID_ACTIONS)} 种
  │  达标线:       {PASS_THRESHOLD:.0%}
  │                                                      │
  │  基线均分:     {baseline_score:.1%}                  │
  │  微调后均分:   {tuned_score:.1%}                     │
  │  提升幅度:     {improvement:+.1%}                    │
  │  是否达标:     {'✅ 达标' if tuned_result['passed'] else '❌ 未达标'}
  │                                                      │
  │  模式:         🖥️  GPU
  └──────────────────────────────────────────────────────┘
""")

    # 保存结果 JSON
    report_path = os.path.join(OUTPUT_DIR, "demo_report.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"  📄 完整报告: {report_path}")

    # 输出一条样例的完整流程（trace）
    print(f"\n─── 完整推理链路示例 ───")
    demo_sample = test_samples[0]
    print(f"  工人说: {demo_sample['worker_utterance']}")
    if tuned_preds and len(tuned_preds) > 0:
        demo_pred = tuned_preds[0]
        print(f"  灵脑输出: {json.dumps(demo_pred.get('parsed', {}), ensure_ascii=False, indent=2)}")
        print(f"  期望输出: {json.dumps(demo_sample['expected_output'], ensure_ascii=False, indent=2)}")
        score = score_sample(
            demo_pred.get("parsed"),
            demo_sample["expected_output"],
            demo_sample.get("eval_criteria", {})
        )
        print(f"  评分: {score:.2%}")

    return results


def run_interactive():
    """交互模式：输入工人指令，看灵脑输出"""
    from lingnao.inference import load_model_with_lora, predict_single

    model, processor = load_model_with_lora()

    print("\n🖥️  灵脑 交互模式 (GPU)")
    print("   输入工人指令，看结构化 JSON 输出。输入 'quit' 退出。\n")
    sample_id = 0
    try:
        while True:
            utterance = input("工人说: ").strip()
            if not utterance:
                continue
            if utterance.lower() in ("quit", "exit", "q"):
                break

            sample_id += 1
            sample = {
                "id": f"interactive_{sample_id:03d}",
                "worker_utterance": utterance,
            }
            result = predict_single(model, processor, sample)
            output = json.dumps(result['parsed'], ensure_ascii=False, indent=2) if result['parsed'] else result['raw_output']
            print(f"灵脑: {output}\n")
    except KeyboardInterrupt:
        print("\n👋 退出")


# ═══════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PRJ-01 灵脑 — 工业指令微调 Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_demo.py                     # 读取 PRJ 数据集，跑推理+训练
  python run_demo.py --skip-train        # 只跑基线
  python run_demo.py --interactive       # 交互模式
        """,
    )
    parser.add_argument("--skip-train", action="store_true", help="跳过训练步骤")
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    args = parser.parse_args()

    print("""
  ╔═══════════════════════════════════════════════╗
  ║   PRJ-01 灵脑 — WAM 第一层                   ║
  ║   工业机器人指令理解微调 Demo                  ║
  ║   基座模型: Qwen3-VL-8B-Instruct             ║
  ║   微调方法: QLoRA 4bit                        ║
  ╚═══════════════════════════════════════════════╝
""")

    if args.interactive:
        run_interactive()
    else:
        run_full_demo(skip_train=args.skip_train)
