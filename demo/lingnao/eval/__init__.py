"""
灵脑 — 评测模块
================

遵循 OpenAI Evals 框架的评测系统。
支持 5 种 match type：weighted_field, json_includes, json_fuzzy, exact, model_graded。
指标：accuracy, bootstrap_std, f1_score。

向后兼容：原有的 score_sample() 和 evaluate_dataset() 保持可用。
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union

from .types import (
    EvalConfig, MatchResult, SampleResult, EvalResult, ModelGradedConfig, flatten_fields,
)
from .matchers import (
    BaseMatcher, WeightedFieldMatcher,
    JsonIncludesMatcher, JsonFuzzyMatcher, ExactMatchMatcher,
)
from .metrics import (
    compute_accuracy, compute_bootstrap_std, compute_macro_f1, compute_f1_score,
)


# ═══════════════════════════════════════════════════════════
# A 区：JSON 解析工具函数（保持不动）
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
# B 区：Eval 类 — OpenAI Evals 风格的主接口
# ═══════════════════════════════════════════════════════════

class Eval:
    """
    评测执行器，对应 OpenAI Evals 框架的一个 eval 实例。

    Usage:
        # 从 YAML 加载
        evaluator = Eval.from_yaml("eval_config.yaml", task_type="取料放置")
        result = evaluator.run(predictions, ground_truth)

        # 手动配置
        config = EvalConfig(id="custom", match_type="weighted_field",
                            args={"must_match": ["action"], "optional": ["force"]})
        evaluator = Eval(config)
        result = evaluator.run(predictions, ground_truth)

        # 输出
        print(result.to_json())
        result.save("outputs/eval_result.json")
    """

    def __init__(
        self,
        config: EvalConfig,
        matcher: Optional[BaseMatcher] = None,
    ):
        self.config = config
        self._matcher = matcher

    @property
    def matcher(self) -> BaseMatcher:
        if self._matcher is None:
            self._matcher = _instantiate_matcher(self.config)
        return self._matcher

    # ── 单样本评测 ──────────────────────────────────────

    def run_sample(
        self,
        predicted: Optional[Dict],
        expected: Dict,
        eval_criteria: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ) -> SampleResult:
        """
        对单个样本进行评测。

        Args:
            predicted: 模型预测（已解析的 JSON 或 None）
            expected: 期望输出 JSON
            eval_criteria: 样本级评测标准（优先于 config.args）
            context: 额外上下文（如 worker_utterance, world_state 供 model_graded 使用）

        Returns:
            SampleResult
        """
        # 使用样本级 criteria 还是 config 级 args？
        if eval_criteria and eval_criteria.get("match_type") == "exact_field_match":
            # 数据集中自带的 criteria → 构建临时 WeightedFieldMatcher
            matcher = WeightedFieldMatcher(
                must_match=eval_criteria.get("must_match", []),
                optional=eval_criteria.get("optional", []),
                pass_threshold=self.config.pass_threshold,
            )
        else:
            matcher = self.matcher

        parsed_ok = predicted is not None
        match_result = matcher.match(predicted, expected, context=context or {})

        return SampleResult(
            id="",  # 由 caller 填充
            score=match_result.score,
            passed=match_result.passed,
            parsed_ok=parsed_ok,
            match_details=match_result.details,
        )

    # ── 数据集评测 ──────────────────────────────────────

    def run(
        self,
        predictions: List[Dict],
        ground_truth: List[Dict],
    ) -> EvalResult:
        """
        对完整数据集进行评测。

        Args:
            predictions: 模型预测列表
                [{"id": ..., "raw_output": ..., "parsed": {...}}, ...]
            ground_truth: 标注列表
                [{"id": ..., "task_type": ..., "expected_output": {...}, "eval_criteria": {...}}, ...]

        Returns:
            EvalResult 包含所有指标和逐样本详情
        """
        # 按 ID 建立 ground_truth 索引
        gt_index = {s["id"]: s for s in ground_truth}

        samples: List[SampleResult] = []
        per_task_type: Dict[str, Dict] = {}
        format_ok = 0
        all_scores: List[float] = []
        f1_data: List[Tuple[Optional[Dict], Dict]] = []

        for pred in predictions:
            sid = pred.get("id", "")
            gt = gt_index.get(sid)

            if gt is None:
                samples.append(SampleResult(
                    id=sid, score=0.0, passed=False,
                    error="ground_truth not found",
                ))
                continue

            # 解析预测
            parsed = pred.get("parsed")
            if isinstance(parsed, str):
                parsed = safe_parse_json(parsed)

            if parsed is not None:
                format_ok += 1

            # 构建 context（供 model_graded 使用）
            context = {
                "worker_utterance": gt.get("worker_utterance", ""),
                "world_state": gt.get("world_state", {}),
            }

            eval_criteria = gt.get("eval_criteria", {})
            sample = self.run_sample(
                parsed, gt["expected_output"],
                eval_criteria=eval_criteria,
                context=context,
            )
            sample.id = sid
            sample.task_type = gt.get("task_type", "unknown")

            samples.append(sample)
            all_scores.append(sample.score)
            f1_data.append((parsed, gt["expected_output"]))

            # 按任务类型统计
            tt = sample.task_type
            if tt not in per_task_type:
                per_task_type[tt] = {"count": 0, "scores": []}
            per_task_type[tt]["count"] += 1
            per_task_type[tt]["scores"].append(sample.score)

        n = len(samples)

        # 汇总 per_task_type
        for tt in per_task_type:
            scores = per_task_type[tt]["scores"]
            per_task_type[tt]["avg"] = round(sum(scores) / len(scores), 4) if scores else 0.0
            per_task_type[tt]["passed"] = per_task_type[tt]["avg"] >= self.config.pass_threshold
            del per_task_type[tt]["scores"]

        # 计算指标
        bs_params = self.config.args
        n_bootstrap = bs_params.get("_bootstrap_samples", 1000)
        ci = bs_params.get("_bootstrap_confidence", 0.95)

        accuracy = compute_accuracy(samples, self.config.pass_threshold)
        bootstrap = compute_bootstrap_std(all_scores, n_bootstrap=n_bootstrap, ci=ci)
        macro_f1 = compute_macro_f1(f1_data)

        # Average score (legacy metric, kept as alternate view)
        avg_score = sum(all_scores) / n if n > 0 else 0.0

        metrics = {}
        if "accuracy" in self.config.metrics:
            metrics["accuracy"] = round(accuracy, 4)
        if "bootstrap_std" in self.config.metrics:
            metrics.update({f"bootstrap_{k}": round(v, 4) for k, v in bootstrap.items()})
        if "f1_score" in self.config.metrics:
            metrics["f1_score"] = round(macro_f1, 4)
        # Always include legacy avg_score for backward compat
        metrics["avg_score"] = round(avg_score, 4)

        # 收集错误样本（score < 1.0）
        errors = []
        for s in samples:
            if s.score < 1.0:
                gt = gt_index.get(s.id, {})
                errors.append({
                    "id": s.id,
                    "score": s.score,
                    "task_type": s.task_type,
                    "expected": gt.get("expected_output", {}),
                    "predicted": next(
                        (p.get("parsed") for p in predictions if p.get("id") == s.id),
                        None
                    ),
                })

        return EvalResult(
            config_id=self.config.id,
            total=n,
            metrics=metrics,
            samples=samples,
            per_task_type=per_task_type,
            errors=errors[:10],  # top-10 errors
            format_pass_rate=round(format_ok / n, 4) if n > 0 else 0.0,
            passed=accuracy >= self.config.pass_threshold,
            metadata={
                "pass_threshold": self.config.pass_threshold,
                "match_type": self.config.match_type,
                "timestamp": datetime.now().isoformat(),
            },
        )

    # ── 工厂方法 ────────────────────────────────────────

    @classmethod
    def from_yaml(
        cls, yaml_path: str, task_type: Optional[str] = None
    ) -> "Eval":
        """从 YAML 配置文件创建 Eval 实例。"""
        config = EvalConfig.from_yaml(yaml_path, task_type=task_type)
        return cls(config)


# ═══════════════════════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════════════════════

def _instantiate_matcher(config: EvalConfig) -> BaseMatcher:
    """根据 EvalConfig 实例化对应的 matcher。"""
    # 对于 model_graded，尝试导入真实实现
    if config.match_type == "model_graded":
        try:
            from .model_graded import ModelGradedMatcher as RealModelGradedMatcher
            mg = config.model_graded or ModelGradedConfig()
            return RealModelGradedMatcher(
                choice_strings=mg.choice_strings,
                choice_scores=mg.choice_scores,
                strategy=mg.strategy,
                prompt_template=mg.prompt_template,
                pass_threshold=config.pass_threshold,
            )
        except ImportError:
            pass

    return BaseMatcher.from_config(config)


def _convert_evalresult_to_legacy_dict(
    result: EvalResult, pass_threshold: float
) -> Dict:
    """
    将 EvalResult 转换为旧版 evaluate_dataset() 返回的 dict 格式，
    确保 run_demo.py 等现有调用方无需修改。

    Keys expected by run_demo.py:
      total, avg_score, passed, pass_threshold, format_pass_rate,
      per_sample, per_task_type, errors
    """
    return {
        "total": result.total,
        "avg_score": result.metrics.get("avg_score", 0.0),
        "passed": result.passed,
        "pass_threshold": pass_threshold,
        "format_pass_rate": result.format_pass_rate,
        "per_sample": [
            {
                "id": s.id,
                "score": s.score,
                "task_type": s.task_type,
                "parsed_ok": s.parsed_ok,
            }
            for s in result.samples
        ],
        "per_task_type": result.per_task_type,
        "errors": result.errors,
    }


# ═══════════════════════════════════════════════════════════
# C 区：增强的 print_report()
# ═══════════════════════════════════════════════════════════

def print_report(result: Union[Dict, EvalResult], save_json: bool = False):
    """
    打印人类可读的评测报告，支持旧版 dict 和新的 EvalResult。

    Args:
        result: evaluate_dataset() 返回的 dict，或 Eval.run() 返回的 EvalResult
        save_json: 是否同时保存 JSON 报告到 outputs/
    """
    # 统一为 dict
    if isinstance(result, EvalResult):
        d = result.to_dict()
        metrics = result.metrics
        samples = result.samples
    else:
        d = result
        metrics = {"avg_score": d.get("avg_score", 0.0)}
        samples = d.get("per_sample", [])

    n = d.get("total", 0)
    avg_score = metrics.get("avg_score", d.get("avg_score", 0.0))
    threshold = d.get("pass_threshold", d.get("metadata", {}).get("pass_threshold", 0.88))
    passed = d.get("passed", False)
    format_rate = d.get("format_pass_rate", 0.0)
    per_tt = d.get("per_task_type", {})
    errors = d.get("errors", [])

    print()
    print("=" * 60)
    print("  PRJ-01 灵脑 — 评测报告")
    print("=" * 60)
    print(f"  总样本数:     {n}")
    print(f"  达标线:       {threshold:.0%}")
    print(f"  是否达标:     {'✅ 达标' if passed else '❌ 未达标'}")
    print(f"  JSON 解析率:  {format_rate:.1%}")
    print()

    # 指标
    if metrics:
        print("─── 指标 (OpenAI Evals) ───")
        for key, val in metrics.items():
            if isinstance(val, float):
                print(f"  {key:<25} {val:.4f}")
            else:
                print(f"  {key:<25} {val}")
        print()

    # 按任务类型
    if per_tt:
        print("─── 按任务类型 ───")
        print(f"  {'任务类型':<12} {'样本数':<8} {'均分':<10} {'达标'}")
        print(f"  {'─'*12} {'─'*8} {'─'*10} {'─'*6}")
        for tt, stats in sorted(per_tt.items()):
            flag = "✅" if stats.get("passed", False) else "❌"
            avg = stats.get("avg", 0.0)
            count = stats.get("count", 0)
            print(f"  {tt:<12} {count:<8} {avg:.1%}       {flag}")

    # 错误样本
    if errors:
        print(f"\n─── 错误样本（前 {len(errors)} 条） ───")
        for err in errors:
            print(f"  [{err.get('id', '?')}] score={err.get('score', 0):.2f}")
            exp = err.get("expected", {})
            pred = err.get("predicted", None)
            print(f"    expected:  {json.dumps(exp, ensure_ascii=False)[:120]}")
            print(f"    predicted: {json.dumps(pred, ensure_ascii=False) if pred else 'None'}")

    print("=" * 60)

    # 可选：保存 JSON 报告
    if save_json:
        from ..config import OUTPUT_DIR
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(OUTPUT_DIR, f"eval_report_{timestamp}.json")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        if isinstance(result, EvalResult):
            result.save(report_path)
        else:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2, default=str)
        print(f"  📄 JSON 报告已保存: {report_path}")


# ═══════════════════════════════════════════════════════════
# D 区：向后兼容包装器
# ═══════════════════════════════════════════════════════════

def score_sample(predicted: Optional[Dict], expected: Dict, criteria: Dict) -> float:
    """
    [兼容] 单条样本评分 [0, 1]。

    保留原有函数签名，内部委托给 WeightedFieldMatcher。
    与旧版 evaluator.py 的 score_sample() 行为完全一致。

    Args:
        predicted: 模型预测的 JSON（可能为 None）
        expected: 期望的 JSON
        criteria: {"must_match": [...], "optional": [...]}

    Returns:
        0-1 之间的分数
    """
    matcher = WeightedFieldMatcher(
        must_match=criteria.get("must_match", []),
        optional=criteria.get("optional", []),
    )
    return matcher.match(predicted, expected).score


def evaluate_dataset(
    predictions: List[Dict],
    ground_truth: List[Dict],
    pass_threshold: float = 0.88,
) -> Dict:
    """
    [兼容] 完整评测流程。

    保留原有函数签名，内部委托给 Eval 类。
    返回的 dict 结构与旧版完全一致，run_demo.py 无需修改。

    Args:
        predictions: 模型预测列表 [{"id": ..., "raw_output": ..., "parsed": {...}}, ...]
        ground_truth: 真实标注列表
        pass_threshold: 达标线

    Returns:
        {total, avg_score, passed, pass_threshold, format_pass_rate, per_sample, per_task_type, errors}
    """
    config = EvalConfig(
        id="legacy_dataset_eval",
        metrics=["accuracy", "bootstrap_std", "f1_score"],
        match_type="weighted_field",
        pass_threshold=pass_threshold,
        args={},
    )
    evaluator = Eval(config)
    result = evaluator.run(predictions, ground_truth)
    return _convert_evalresult_to_legacy_dict(result, pass_threshold)


# ═══════════════════════════════════════════════════════════
# E 区：CLI（增强版）
# ═══════════════════════════════════════════════════════════

def main():
    """CLI 入口：python -m lingnao.eval --preds <file> [options]"""
    import argparse
    import sys

    from ..config import TEST_FILE, EVAL_CONFIG_YAML

    parser = argparse.ArgumentParser(description="PRJ-01 灵脑 — 评测（OpenAI Evals 标准）")
    parser.add_argument("--preds", required=True, help="模型预测文件 (JSONL)")
    parser.add_argument("--test", default=TEST_FILE, help="测试集标注文件")
    parser.add_argument("--threshold", type=float, default=0.88)
    parser.add_argument("--config", default=EVAL_CONFIG_YAML,
                        help="Eval YAML 配置文件路径")
    parser.add_argument("--match-type", default=None,
                        choices=["weighted_field", "json_includes", "json_fuzzy", "exact", "model_graded"],
                        help="覆盖 YAML 中的 match_type")
    parser.add_argument("--task-type", default=None,
                        help="指定任务类型（使用对应的 per_task_type 配置）")
    parser.add_argument("--save-json", action="store_true",
                        help="保存评测结果为 JSON 文件")
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

    # 构建 Eval
    if os.path.exists(args.config):
        evaluator = Eval.from_yaml(args.config, task_type=args.task_type)
        if args.match_type:
            evaluator.config.match_type = args.match_type
        evaluator.config.pass_threshold = args.threshold
    else:
        # 回退到默认 weighted_field
        config = EvalConfig(
            id="cli_eval",
            match_type=args.match_type or "weighted_field",
            pass_threshold=args.threshold,
        )
        evaluator = Eval(config)

    result = evaluator.run(preds, gt)
    print_report(result, save_json=args.save_json)

    # 返回 exit code
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
