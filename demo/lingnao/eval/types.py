"""
灵脑 — 评测类型定义
====================

遵循 OpenAI Evals 框架的数据类定义。
无逻辑依赖，可被所有评测模块安全导入。
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def flatten_fields(obj: Dict, prefix: str = "") -> Dict[str, Any]:
    """
    将嵌套 dict 展开为点号路径的扁平字典。

    Example:
        flatten_fields({"a": {"b": 1}, "c": 2}) → {"a.b": 1, "c": 2}
    """
    result = {}
    for k, v in obj.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict) and v:
            result.update(flatten_fields(v, key))
        else:
            result[key] = v
    return result


# ═══════════════════════════════════════════════════════════
# 配置数据类
# ═══════════════════════════════════════════════════════════

@dataclass
class ModelGradedConfig:
    """LLM-as-Judge 评测配置，对应 OpenAI Evals modelgraded 参数。"""
    model_name: str = "qwen3-vl-8b"
    strategy: str = "classify"                        # classify | cot_classify | classify_cot
    choice_strings: List[str] = field(default_factory=lambda: ["正确", "部分正确", "错误"])
    choice_scores: List[float] = field(default_factory=lambda: [1.0, 0.5, 0.0])
    prompt_template: str = ""
    max_tokens: int = 256
    temperature: float = 0.0


@dataclass
class EvalConfig:
    """
    单次评测的完整配置，对应 OpenAI Evals YAML 中的一个 eval 条目。

    Attributes:
        id: 评测唯一标识
        metrics: 需要计算的指标列表，如 ["accuracy", "bootstrap_std", "f1_score"]
        match_type: 匹配类型 — weighted_field | json_includes | json_fuzzy | exact | model_graded
        args: 传给 matcher 的参数（如 must_match, optional 列表）
        pass_threshold: 达标线 [0, 1]
        model_graded: LLM-as-Judge 配置（仅 match_type=model_graded 时生效）
    """
    id: str = "lingnao_eval"
    metrics: List[str] = field(default_factory=lambda: ["accuracy", "bootstrap_std", "f1_score"])
    match_type: str = "weighted_field"
    args: Dict[str, Any] = field(default_factory=dict)
    pass_threshold: float = 0.88
    model_graded: Optional[ModelGradedConfig] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EvalConfig":
        """从字典构建 EvalConfig。"""
        mg = d.get("model_graded")
        return cls(
            id=d.get("id", "lingnao_eval"),
            metrics=d.get("metrics", ["accuracy"]),
            match_type=d.get("match_type", "weighted_field"),
            args=d.get("args", {}),
            pass_threshold=d.get("pass_threshold", 0.88),
            model_graded=ModelGradedConfig(**mg) if mg else None,
        )

    @classmethod
    def from_yaml(cls, yaml_path: str, task_type: Optional[str] = None) -> "EvalConfig":
        """
        从 YAML 配置文件加载评测配置。

        如果指定 task_type，会合并 per_task_type 中的覆盖项。
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML is required for YAML config loading. pip install pyyaml")

        with open(yaml_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        defaults = raw.get("defaults", {})

        config_dict = {
            "id": f"lingnao_{task_type}" if task_type else "lingnao_eval",
            "metrics": defaults.get("metrics", ["accuracy"]),
            "match_type": "weighted_field",
            "pass_threshold": defaults.get("pass_threshold", 0.88),
        }

        # 合并 per_task_type 配置
        if task_type and "per_task_type" in raw:
            tt_cfg = raw["per_task_type"].get(task_type, {})
            if tt_cfg:
                config_dict["match_type"] = tt_cfg.get("match_type", config_dict["match_type"])
                config_dict["args"] = tt_cfg.get("args", {})
                config_dict["pass_threshold"] = tt_cfg.get("pass_threshold", config_dict["pass_threshold"])

        # model_graded
        mg_cfg = raw.get("match_types", {}).get("model_graded", {})
        if config_dict["match_type"] == "model_graded" and mg_cfg:
            config_dict["model_graded"] = {
                "model_name": mg_cfg.get("model", "qwen3-vl-8b"),
                "strategy": mg_cfg.get("strategy", "classify"),
                "choice_strings": mg_cfg.get("choice_strings", ["正确", "部分正确", "错误"]),
                "choice_scores": mg_cfg.get("choice_scores", [1.0, 0.5, 0.0]),
                "prompt_template": mg_cfg.get("prompt_template", ""),
                "max_tokens": mg_cfg.get("max_tokens", 256),
                "temperature": mg_cfg.get("temperature", 0.0),
            }

        # bootstrap 参数合并到 args
        if "bootstrap" not in config_dict.get("args", {}):
            config_dict.setdefault("args", {})
            config_dict["args"].setdefault("_bootstrap_samples", defaults.get("bootstrap_samples", 1000))
            config_dict["args"].setdefault("_bootstrap_confidence", defaults.get("bootstrap_confidence", 0.95))

        return cls.from_dict(config_dict)


# ═══════════════════════════════════════════════════════════
# 结果数据类
# ═══════════════════════════════════════════════════════════

@dataclass
class MatchResult:
    """
    单次匹配操作的结果。

    Attributes:
        score: [0, 1] 之间的分数
        passed: 是否达标 (score >= pass_threshold)
        details: 匹配详情（字段级结果等）
    """
    score: float
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SampleResult:
    """
    单个样本的评测结果。

    Attributes:
        id: 样本 ID
        score: [0, 1] 之间的分数
        passed: 是否达标
        task_type: 任务类型
        parsed_ok: JSON 解析是否成功
        match_details: 匹配详情
        error: 错误信息（如有）
    """
    id: str
    score: float
    passed: bool
    task_type: str = "unknown"
    parsed_ok: bool = True
    match_details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class EvalResult:
    """
    完整评测结果，对应一次 Eval.run() 调用。

    Attributes:
        config_id: 评测配置 ID
        total: 总样本数
        metrics: 计算出的指标值，如 {"accuracy": 0.92, "bootstrap_std": 0.015, "f1_score": 0.88}
        samples: 每个样本的详细结果
        per_task_type: 按任务类型分组的统计
        errors: 错误样本列表（score < 1.0 的样本）
        format_pass_rate: JSON 解析成功率
        passed: 整体是否达标
        metadata: 额外元数据
    """
    config_id: str
    total: int
    metrics: Dict[str, float] = field(default_factory=dict)
    samples: List[SampleResult] = field(default_factory=list)
    per_task_type: Dict[str, Dict] = field(default_factory=dict)
    errors: List[Dict] = field(default_factory=list)
    format_pass_rate: float = 0.0
    passed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转为字典，便于 JSON 序列化。"""
        return {
            "config_id": self.config_id,
            "total": self.total,
            "metrics": self.metrics,
            "samples": [asdict(s) for s in self.samples],
            "per_task_type": self.per_task_type,
            "errors": self.errors,
            "format_pass_rate": self.format_pass_rate,
            "passed": self.passed,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """转为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=str)

    def save(self, path: str):
        """保存评测结果为 JSON 文件。"""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
