"""
灵脑 — 匹配器实现
==================

遵循 OpenAI Evals 框架的 match type 体系。
每个 matcher 实现 match(predicted, expected) → MatchResult 接口。
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, ClassVar
from .types import MatchResult, EvalConfig


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def _get_nested(obj: Dict, path: str) -> Any:
    """按点号路径获取嵌套字段值。返回 None 如果路径不存在。"""
    if obj is None:
        return None
    keys = path.split(".")
    current = obj
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return None
    return current


def _flatten_fields(obj: Dict, prefix: str = "") -> Dict[str, Any]:
    """将嵌套 dict 展开为点号路径的扁平字典。"""
    from .types import flatten_fields
    return flatten_fields(obj, prefix)


# ═══════════════════════════════════════════════════════════
# 抽象基类
# ═══════════════════════════════════════════════════════════

class BaseMatcher(ABC):
    """所有 matcher 的抽象基类，遵循 OpenAI Evals 模式。"""

    match_type: ClassVar[str]

    @abstractmethod
    def match(self, predicted: Any, expected: Any, **kwargs) -> MatchResult:
        """
        对单次预测进行评分。

        Args:
            predicted: 模型预测输出（已解析的 JSON 或 None）
            expected: 期望输出
            **kwargs: 额外上下文（如 sample, criteria 等）

        Returns:
            MatchResult with score in [0, 1]
        """
        ...

    @classmethod
    def from_config(cls, config: EvalConfig) -> "BaseMatcher":
        """工厂方法：从 EvalConfig 实例化正确的 matcher。"""
        registry = {
            "weighted_field": WeightedFieldMatcher,
            "json_includes": JsonIncludesMatcher,
            "json_fuzzy": JsonFuzzyMatcher,
            "exact": ExactMatchMatcher,
            "model_graded": ModelGradedMatcher,
        }
        matcher_cls = registry.get(config.match_type)
        if matcher_cls is None:
            raise ValueError(f"Unknown match_type: {config.match_type}. "
                             f"Must be one of: {list(registry.keys())}")
        return matcher_cls(**config.args)


# ═══════════════════════════════════════════════════════════
# Match 类型实现
# ═══════════════════════════════════════════════════════════

class WeightedFieldMatcher(BaseMatcher):
    """
    加权字段匹配 — 保留灵脑原始的 must_match/optional 评分逻辑。

    对应 OpenAI Evals 的 "JsonMatch" 的增强版：允许对安全关键字段
    施加更高权重（must_weight=1.0），非关键字段较低权重（optional_weight=0.5）。

    Formula:
        score = (must_correct × W_must + opt_correct × W_opt)
              / (n_must × W_must + n_opt × W_opt)

    这是灵脑独有的评测原语，在 OpenAI Evals 标准 match type 体系中作为
    工业场景的扩展。
    """

    match_type = "weighted_field"

    def __init__(
        self,
        must_match: Optional[List[str]] = None,
        optional: Optional[List[str]] = None,
        must_weight: float = 1.0,
        optional_weight: float = 0.5,
        pass_threshold: float = 0.88,
    ):
        self.must_match = must_match or []
        self.optional = optional or []
        self.must_weight = must_weight
        self.optional_weight = optional_weight
        self.pass_threshold = pass_threshold

    def match(self, predicted: Any, expected: Any, **kwargs) -> MatchResult:
        if predicted is None:
            return MatchResult(
                score=0.0,
                passed=False,
                details={"reason": "predicted is None (JSON parse failure)"},
            )

        n_must = len(self.must_match)
        n_opt = len(self.optional)

        # 无指定字段时回退到整体 JSON 比对
        if n_must == 0 and n_opt == 0:
            eq = predicted == expected
            return MatchResult(
                score=1.0 if eq else 0.0,
                passed=eq,
                details={"method": "full_json_equality"},
            )

        # 逐字段比对
        field_results = {}

        must_correct = 0
        for f in self.must_match:
            pred_val = _get_nested(predicted, f)
            exp_val = _get_nested(expected, f)
            is_correct = pred_val == exp_val
            if is_correct:
                must_correct += 1
            field_results[f] = {
                "predicted": pred_val, "expected": exp_val,
                "correct": is_correct, "weight": self.must_weight,
            }

        opt_correct = 0
        for f in self.optional:
            pred_val = _get_nested(predicted, f)
            exp_val = _get_nested(expected, f)
            # optional 字段：pred 存在且值正确才算正确
            is_correct = (pred_val is not None) and (pred_val == exp_val)
            if is_correct:
                opt_correct += 1
            field_results[f] = {
                "predicted": pred_val, "expected": exp_val,
                "correct": is_correct, "weight": self.optional_weight,
            }

        denominator = n_must * self.must_weight + n_opt * self.optional_weight
        numerator = must_correct * self.must_weight + opt_correct * self.optional_weight
        score = numerator / denominator if denominator > 0 else 0.0

        return MatchResult(
            score=round(score, 6),
            passed=score >= self.pass_threshold,
            details={
                "must_correct": must_correct,
                "n_must": n_must,
                "opt_correct": opt_correct,
                "n_opt": n_opt,
                "must_weight": self.must_weight,
                "optional_weight": self.optional_weight,
                "field_results": field_results,
            },
        )


class JsonIncludesMatcher(BaseMatcher):
    """
    JSON 包含匹配 — 对应 OpenAI Evals 的 "Includes" 类型。

    逻辑：期望输出的所有字段必须在预测输出中存在且值相等。
    预测输出可以有额外字段（不被扣分）。

    适用场景：模型输出包含额外上下文信息，但核心指令正确的场合。
    """

    match_type = "json_includes"

    def __init__(self, pass_threshold: float = 0.88):
        self.pass_threshold = pass_threshold

    def match(self, predicted: Any, expected: Any, **kwargs) -> MatchResult:
        if predicted is None or expected is None:
            return MatchResult(
                score=0.0,
                passed=False,
                details={"reason": "predicted or expected is None"},
            )

        expected_flat = _flatten_fields(expected)
        predicted_flat = _flatten_fields(predicted)

        if not expected_flat:
            eq = predicted == expected
            return MatchResult(score=1.0 if eq else 0.0, passed=eq)

        matched = 0
        field_results = {}
        for k, v in expected_flat.items():
            pv = predicted_flat.get(k)
            is_correct = (k in predicted_flat and pv == v)
            if is_correct:
                matched += 1
            field_results[k] = {"predicted": pv, "expected": v, "correct": is_correct}

        total = len(expected_flat)
        score = matched / total

        return MatchResult(
            score=round(score, 6),
            passed=score >= self.pass_threshold,
            details={
                "matched": matched,
                "total": total,
                "field_results": field_results,
            },
        )


class JsonFuzzyMatcher(BaseMatcher):
    """
    JSON 模糊匹配 — 对应 OpenAI Evals 的 "FuzzyMatch" 类型。

    逻辑：对字符串字段执行双向包含检查 (a in b or b in a)，
    对非字符串字段执行精确匹配。

    适用场景：自由文本字段允许措辞变体，但结构化字段仍需精确匹配。
    """

    match_type = "json_fuzzy"

    def __init__(self, fuzzy_fields: Optional[List[str]] = None,
                 pass_threshold: float = 0.88):
        self.fuzzy_fields = fuzzy_fields or []
        self.pass_threshold = pass_threshold

    def match(self, predicted: Any, expected: Any, **kwargs) -> MatchResult:
        if predicted is None or expected is None:
            return MatchResult(
                score=0.0,
                passed=False,
                details={"reason": "predicted or expected is None"},
            )

        expected_flat = _flatten_fields(expected)
        predicted_flat = _flatten_fields(predicted)

        if not expected_flat:
            eq = predicted == expected
            return MatchResult(score=1.0 if eq else 0.0, passed=eq)

        matched = 0
        field_results = {}
        for k, ev in expected_flat.items():
            pv = predicted_flat.get(k)
            if k in self.fuzzy_fields and isinstance(ev, str) and isinstance(pv, str):
                is_correct = (ev in pv) or (pv in ev)
            else:
                is_correct = (pv == ev)
            if is_correct:
                matched += 1
            field_results[k] = {
                "predicted": pv, "expected": ev,
                "correct": is_correct, "fuzzy": k in self.fuzzy_fields,
            }

        total = len(expected_flat)
        score = matched / total

        return MatchResult(
            score=round(score, 6),
            passed=score >= self.pass_threshold,
            details={
                "matched": matched,
                "total": total,
                "field_results": field_results,
            },
        )


class ExactMatchMatcher(BaseMatcher):
    """
    精确匹配 — 对应 OpenAI Evals 的 "Match" 类型。

    逻辑：predicted JSON 必须与 expected JSON 完全等同。
    最严格的匹配器，不允许任何差异。

    适用场景：换线、状态查询等必须精确匹配的指令。
    """

    match_type = "exact"

    def __init__(self, pass_threshold: float = 1.0):
        self.pass_threshold = pass_threshold

    def match(self, predicted: Any, expected: Any, **kwargs) -> MatchResult:
        if predicted is None:
            return MatchResult(
                score=0.0,
                passed=False,
                details={"reason": "predicted is None (JSON parse failure)"},
            )
        eq = predicted == expected
        return MatchResult(
            score=1.0 if eq else 0.0,
            passed=eq,
            details={"match_type": "exact", "equal": eq},
        )


# ═══════════════════════════════════════════════════════════
# ModelGradedMatcher — 延迟导入避免循环
# ═══════════════════════════════════════════════════════════

class ModelGradedMatcher(BaseMatcher):
    """
    LLM 做法官评测 — 对应 OpenAI Evals 的 "ModelGraded" 类型。

    接受 callable model_fn(prompt) → str，解耦模型加载。
    三种策略：classify, cot_classify, classify_cot。

    NOTE: 完整实现在 eval_model_graded.py 中。
    此处为占位符，实际使用时从 eval_model_graded 导入。
    """

    match_type = "model_graded"

    def __init__(self, **kwargs):
        self._config = kwargs

    def match(self, predicted: Any, expected: Any, **kwargs) -> MatchResult:
        """占位实现 — 实际使用需从 eval_model_graded 导入完整版。"""
        raise NotImplementedError(
            "ModelGradedMatcher 需要从 eval_model_graded 导入完整实现。"
            "请使用: from lingnao.eval.model_graded import ModelGradedMatcher"
        )
