"""
灵脑 — 评测模块
================

技术方案第七节：严格 JSON 字段级匹配评测。
不依赖 LLM-as-Judge，纯字段比对，确定性可复现。

达标线：100 条测试集平均分 ≥ 0.88
"""

import json
import re
from typing import Dict, List, Tuple, Optional, Any


def safe_parse_json(text: str) -> Optional[Dict]:
    """
    从模型原始输出中安全提取 JSON。

    与技术方案 7.4 一致：逐级降级解析。
    """
    if not text:
        return None

    # 1. 直接 parse
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. 找 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. 找第一个 { 到最后一个 } 之间的内容
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s:e + 1])
        except (json.JSONDecodeError, ValueError):
            pass

    # 4. 解析失败
    return None


def get_nested(obj: Dict, path: str) -> Any:
    """
    按点号路径获取嵌套字段值。

    Example:
        get_nested({"a": {"b": 1}}, "a.b") → 1
    """
    keys = path.split(".")
    current = obj
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return None
    return current


def score_sample(predicted: Optional[Dict], expected: Dict, criteria: Dict) -> float:
    """
    单条样本评分 [0, 1]。

    规则（与技术方案 7.2 一致）：
      - must_match 字段错了扣全分
      - optional 字段对了加分，错了不扣
      - 总分 = (must_correct + 0.5 × opt_correct) / (n_must + 0.5 × n_opt)

    Args:
        predicted: 模型预测的 JSON（可能为 None）
        expected: 期望的 JSON
        criteria: {"must_match": [...], "optional": [...]}

    Returns:
        0-1 之间的分数
    """
    if predicted is None:
        return 0.0

    must = criteria.get("must_match", [])
    opt = criteria.get("optional", [])

    n_must = len(must)
    n_opt = len(opt)

    if n_must == 0 and n_opt == 0:
        # 没有指定评测字段，回退到整体 JSON 比对
        return 1.0 if predicted == expected else 0.0

    must_correct = sum(
        1 for f in must
        if get_nested(predicted, f) == get_nested(expected, f)
    )
    opt_correct = sum(
        1 for f in opt
        if get_nested(predicted, f) == get_nested(expected, f)
        and get_nested(predicted, f) is not None
    )

    denominator = n_must + 0.5 * n_opt
    numerator = must_correct + 0.5 * opt_correct

    return numerator / denominator if denominator > 0 else 0.0


def evaluate_dataset(
    predictions: List[Dict],
    ground_truth: List[Dict],
    pass_threshold: float = 0.88,
) -> Dict:
    """
    完整评测流程。

    Args:
        predictions: 模型预测列表 [{"id": ..., "raw_output": ..., "parsed": {...}}, ...]
        ground_truth: 真实标注列表 [{"id": ..., "expected_output": {...}, "eval_criteria": {...}}, ...]
        pass_threshold: 达标线

    Returns:
        {
            "total": int,
            "avg_score": float,
            "passed": bool,
            "pass_threshold": float,
            "format_pass_rate": float,
            "per_sample": [...],
            "per_task_type": {...},
            "errors": [...],
        }
    """
    # 按 ID 建立 ground_truth 索引
    gt_index = {s["id"]: s for s in ground_truth}

    per_sample = []
    per_task_type = {}
    format_ok = 0
    total_score = 0.0

    for pred in predictions:
        sid = pred.get("id", "")
        gt = gt_index.get(sid)

        if gt is None:
            per_sample.append({
                "id": sid,
                "score": 0.0,
                "error": "ground_truth not found",
            })
            continue

        parsed = pred.get("parsed")
        if isinstance(parsed, str):
            parsed = safe_parse_json(parsed)

        if parsed is not None:
            format_ok += 1

        score = score_sample(parsed, gt["expected_output"], gt.get("eval_criteria", {}))
        per_sample.append({
            "id": sid,
            "score": score,
            "task_type": gt.get("task_type", "unknown"),
            "parsed_ok": parsed is not None,
        })

        # 按任务类型统计
        tt = gt.get("task_type", "unknown")
        if tt not in per_task_type:
            per_task_type[tt] = {"scores": [], "count": 0}
        per_task_type[tt]["scores"].append(score)
        per_task_type[tt]["count"] += 1

        total_score += score

    n = len(per_sample)
    avg_score = total_score / n if n > 0 else 0.0

    # 汇总每类任务
    for tt in per_task_type:
        scores = per_task_type[tt]["scores"]
        per_task_type[tt]["avg"] = sum(scores) / len(scores) if scores else 0.0
        per_task_type[tt]["passed"] = per_task_type[tt]["avg"] >= pass_threshold
        del per_task_type[tt]["scores"]

    # 找出错误样本（score < 1.0）
    errors = [
        {
            "id": s["id"],
            "score": s["score"],
            "expected": gt_index.get(s["id"], {}).get("expected_output", {}),
            "predicted": next(
                (p.get("parsed") for p in predictions if p.get("id") == s["id"]),
                None
            ),
        }
        for s in per_sample if s["score"] < 1.0
    ]

    return {
        "total": n,
        "avg_score": round(avg_score, 4),
        "passed": avg_score >= pass_threshold,
        "pass_threshold": pass_threshold,
        "format_pass_rate": round(format_ok / n, 4) if n > 0 else 0.0,
        "per_sample": per_sample,
        "per_task_type": per_task_type,
        "errors": errors[:10],  # 只保留前 10 个错误
    }


def print_report(result: Dict):
    """打印人类可读的评测报告"""
    print()
    print("=" * 60)
    print("  PRJ-01 灵脑 — 评测报告")
    print("=" * 60)
    print(f"  总样本数:     {result['total']}")
    print(f"  平均分:       {result['avg_score']:.2%}")
    print(f"  达标线:       {result['pass_threshold']:.0%}")
    print(f"  是否达标:     {'✅ 达标' if result['passed'] else '❌ 未达标'}")
    print(f"  JSON 解析率:  {result['format_pass_rate']:.1%}")
    print()

    if result["per_task_type"]:
        print("─── 按任务类型 ───")
        print(f"  {'任务类型':<12} {'样本数':<8} {'均分':<10} {'达标'}")
        print(f"  {'─'*12} {'─'*8} {'─'*10} {'─'*6}")
        for tt, stats in sorted(result["per_task_type"].items()):
            flag = "✅" if stats["passed"] else "❌"
            print(f"  {tt:<12} {stats['count']:<8} {stats['avg']:.1%}       {flag}")

    if result["errors"]:
        print(f"\n─── 错误样本（前 {len(result['errors'])} 条） ───")
        for err in result["errors"]:
            print(f"  [{err['id']}] score={err['score']:.2f}")
            print(f"    expected:  {json.dumps(err['expected'], ensure_ascii=False)[:120]}")
            print(f"    predicted: {json.dumps(err['predicted'], ensure_ascii=False) if err['predicted'] else 'None'}")

    print("=" * 60)


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config import TEST_FILE

    parser = argparse.ArgumentParser(description="PRJ-01 灵脑 — 评测")
    parser.add_argument("--preds", required=True, help="模型预测文件 (JSONL)")
    parser.add_argument("--test", default=TEST_FILE, help="测试集标注文件")
    parser.add_argument("--threshold", type=float, default=0.88)
    args = parser.parse_args()

    # 加载预测
    preds = []
    with open(args.preds, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                preds.append(json.loads(line))

    # 加载测试集
    gt = []
    with open(args.test, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                gt.append(json.loads(line))

    result = evaluate_dataset(preds, gt, pass_threshold=args.threshold)
    print_report(result)

    # 返回 exit code
    sys.exit(0 if result["passed"] else 1)
