"""
灵脑 — 评测指标计算
====================

遵循 OpenAI Evals 框架的指标计算方式：
  - accuracy:  达标样本占比 (score >= threshold)
  - bootstrap_std: Bootstrap 置信区间
  - f1_score:  字段级精确率/召回率调和均值
"""

import random
from typing import Dict, List, Tuple, Any, Optional

from .eval_types import SampleResult, flatten_fields


# ═══════════════════════════════════════════════════════════
# Accuracy
# ═══════════════════════════════════════════════════════════

def compute_accuracy(
    samples: List[SampleResult],
    threshold: Optional[float] = None,
) -> float:
    """
    计算 accuracy = 达标样本占比。

    Args:
        samples: 评测结果列表
        threshold: 达标线。None 时使用每个 sample 自身的 passed 字段。

    Returns:
        accuracy ∈ [0, 1]
    """
    if not samples:
        return 0.0
    if threshold is not None:
        return sum(1 for s in samples if s.score >= threshold) / len(samples)
    return sum(1 for s in samples if s.passed) / len(samples)


# ═══════════════════════════════════════════════════════════
# Bootstrap 置信区间
# ═══════════════════════════════════════════════════════════

def compute_bootstrap_std(
    scores: List[float],
    n_bootstrap: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> Dict[str, float]:
    """
    Bootstrap 置信区间 for the mean score.

    使用 numpy 加速（如果可用），否则回退到纯 Python 实现。

    Args:
        scores: 评分列表
        n_bootstrap: Bootstrap 重采样次数
        ci: 置信水平 (0 < ci < 1)
        seed: 随机种子（确定性可复现）

    Returns:
        {"mean": float, "std": float, "ci_lower": float, "ci_upper": float}
    """
    n = len(scores)

    if n == 0:
        return {"mean": 0.0, "std": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}

    if n == 1:
        v = scores[0]
        return {"mean": v, "std": 0.0, "ci_lower": v, "ci_upper": v}

    # 优先使用 numpy
    try:
        import numpy as np
        rng = np.random.RandomState(seed)
        means = []
        for _ in range(n_bootstrap):
            indices = rng.randint(0, n, size=n)
            means.append(np.mean([scores[i] for i in indices]))
        means = np.array(means)
        alpha = (1 - ci) / 2
        return {
            "mean": float(np.mean(means)),
            "std": float(np.std(means, ddof=0)),
            "ci_lower": float(np.percentile(means, 100 * alpha)),
            "ci_upper": float(np.percentile(means, 100 * (1 - alpha))),
        }
    except ImportError:
        # 纯 Python 回退
        rng = random.Random(seed)
        means = []
        for _ in range(n_bootstrap):
            sample = [scores[rng.randint(0, n - 1)] for _ in range(n)]
            means.append(sum(sample) / n)
        means.sort()
        alpha = (1 - ci) / 2
        lo_idx = int(len(means) * alpha)
        hi_idx = int(len(means) * (1 - alpha)) - 1
        avg = sum(means) / len(means)
        std = (sum((m - avg) ** 2 for m in means) / len(means)) ** 0.5
        return {
            "mean": avg,
            "std": std,
            "ci_lower": means[max(0, lo_idx)],
            "ci_upper": means[min(len(means) - 1, hi_idx)],
        }


# ═══════════════════════════════════════════════════════════
# F1 Score（字段级）
# ═══════════════════════════════════════════════════════════

def compute_f1_score(predicted: Optional[Dict], expected: Dict) -> float:
    """
    单样本字段级 F1 分数。

    将 JSON 扁平化为键值对，计算：
        precision = TP / (TP + FP)
        recall    = TP / (TP + FN)
        f1        = 2 × P × R / (P + R)

    Args:
        predicted: 模型预测（已解析或 None）
        expected: 期望输出

    Returns:
        F1 ∈ [0, 1]
    """
    if predicted is None:
        return 0.0

    pred_flat = flatten_fields(predicted)
    exp_flat = flatten_fields(expected)

    pred_items = set((k, str(v)) for k, v in pred_flat.items())
    exp_items = set((k, str(v)) for k, v in exp_flat.items())

    tp = len(pred_items & exp_items)
    fp = len(pred_items - exp_items)
    fn = len(exp_items - pred_items)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    return f1


def compute_macro_f1(
    samples_data: List[Tuple[Optional[Dict], Dict]],
) -> float:
    """
    聚合 macro-F1 分数：所有样本 F1 的算术平均。

    Args:
        samples_data: [(predicted, expected), ...] 列表

    Returns:
        macro-F1 ∈ [0, 1]
    """
    if not samples_data:
        return 0.0
    f1s = [compute_f1_score(pred, exp) for pred, exp in samples_data]
    return sum(f1s) / len(f1s)
