"""
灵脑 — LLM 做法官评测
======================

遵循 OpenAI Evals 框架的 "ModelGraded" eval 类型。
使用 LLM（Qwen3-VL）作为评判模型，对开放式/高变异输出进行评分。

三种策略（对应 OpenAI Evals）：
  - classify:      直接输出评级（最快）
  - cot_classify:  先推理再评级（推荐，最准）
  - classify_cot:  先评级再解释
"""

import json
import re
from typing import Dict, List, Optional, Any, Callable

from .types import MatchResult, EvalConfig, ModelGradedConfig
from .matchers import BaseMatcher


# ═══════════════════════════════════════════════════════════
# 默认评测 Prompt 模板
# ═══════════════════════════════════════════════════════════

DEFAULT_PROMPT_TEMPLATE = """你是一个工业机器人指令理解评测专家。请判断模型输出的结构化指令是否与期望输出一致。

工人说的话：{worker_utterance}
当前世界状态：{world_state}
期望的 JSON 输出：{ideal}
模型实际输出的 JSON：{completion}

请选择以下评价之一：
- 正确：模型输出与期望完全一致，所有关键字段都正确
- 部分正确：主要操作正确，但部分细节字段有偏差
- 错误：操作类型错误或关键字段严重错误

只输出评价结果（正确/部分正确/错误），不需要输出其他内容。"""


# ═══════════════════════════════════════════════════════════
# ModelGradedMatcher
# ═══════════════════════════════════════════════════════════

class ModelGradedMatcher(BaseMatcher):
    """
    LLM 做法官评测 — 对应 OpenAI Evals 的 ModelGraded 类型。

    使用 callable model_fn(prompt) → str 解耦模型加载。
    调用方可注入任意兼容的模型函数。

    Usage:
        judge = ModelGradedMatcher(
            choice_strings=["正确", "部分正确", "错误"],
            choice_scores=[1.0, 0.5, 0.0],
            strategy="classify",
            model_fn=my_model_fn,
        )
        result = judge.match(predicted, expected, context={...})
    """

    match_type = "model_graded"

    def __init__(
        self,
        choice_strings: Optional[List[str]] = None,
        choice_scores: Optional[List[float]] = None,
        strategy: str = "classify",
        prompt_template: str = "",
        model_fn: Optional[Callable[[str], str]] = None,
        pass_threshold: float = 0.5,
        **kwargs,
    ):
        self.choice_strings = choice_strings or ["正确", "部分正确", "错误"]
        self.choice_scores = choice_scores or [1.0, 0.5, 0.0]
        self.strategy = strategy
        self.prompt_template = prompt_template or DEFAULT_PROMPT_TEMPLATE
        self._model_fn = model_fn
        self.pass_threshold = pass_threshold

        if len(self.choice_strings) != len(self.choice_scores):
            raise ValueError(
                f"choice_strings ({len(self.choice_strings)}) and "
                f"choice_scores ({len(self.choice_scores)}) must have same length"
            )
        if strategy not in ("classify", "cot_classify", "classify_cot"):
            raise ValueError(
                f"Unknown strategy: {strategy}. "
                f"Must be: classify, cot_classify, classify_cot"
            )

    def set_model_fn(self, fn: Callable[[str], str]):
        """注入模型调用函数。fn(prompt: str) -> completion: str"""
        self._model_fn = fn

    @property
    def model_fn(self) -> Callable[[str], str]:
        if self._model_fn is None:
            raise RuntimeError(
                "ModelGradedMatcher.model_fn is not set. "
                "Call set_model_fn() or pass model_fn to constructor."
            )
        return self._model_fn

    def match(self, predicted: Any, expected: Any, **kwargs) -> MatchResult:
        """
        使用 LLM 对单次预测进行评分。

        Kwargs:
            context: Dict with keys matching prompt template placeholders
                     (worker_utterance, world_state, ideal, completion)

        Returns:
            MatchResult with score ∈ choice_scores range
        """
        if predicted is None:
            return MatchResult(
                score=0.0,
                passed=False,
                details={"reason": "predicted is None (JSON parse failure)"},
            )

        context = kwargs.get("context", {})
        prompt = self._render_prompt(predicted, expected, context)
        raw_answer = self.model_fn(prompt)
        choice = self._extract_choice(raw_answer)
        score = self._choice_to_score(choice)

        return MatchResult(
            score=score,
            passed=score >= self.pass_threshold,
            details={
                "raw_answer": raw_answer,
                "extracted_choice": choice,
                "score": score,
                "strategy": self.strategy,
                "choice_strings": self.choice_strings,
                "choice_scores": self.choice_scores,
            },
        )

    def _render_prompt(
        self, predicted: Any, expected: Any, context: Dict[str, Any]
    ) -> str:
        """渲染评测 prompt 模板。"""
        return self.prompt_template.format(
            worker_utterance=context.get("worker_utterance", ""),
            world_state=json.dumps(
                context.get("world_state", {}), ensure_ascii=False
            ),
            ideal=json.dumps(expected, ensure_ascii=False, indent=2),
            completion=json.dumps(predicted, ensure_ascii=False, indent=2),
        )

    def _extract_choice(self, raw: str) -> Optional[str]:
        """
        从 LLM 原始输出中提取评级。

        策略：
          1. 按长度降序精确匹配（长字符串优先，避免 "正确" 误匹配 "部分正确"）
          2. 对 classify_cot / cot_classify：从后往前找包含评级关键词的行
        """
        if not raw:
            return None

        # 按长度降序排序，确保长串优先匹配
        sorted_choices = sorted(self.choice_strings, key=len, reverse=True)

        # 1. 精确匹配
        for c in sorted_choices:
            if c in raw:
                return c

        # 2. 对 classify_cot / cot_classify：从后往前找
        lines = raw.strip().split("\n")
        for line in reversed(lines):
            for c in sorted_choices:
                if c in line:
                    return c

        return None

    def _choice_to_score(self, choice: Optional[str]) -> float:
        """将评级映射为数值分数。"""
        if choice is None:
            return 0.0
        for c, s in zip(self.choice_strings, self.choice_scores):
            if c == choice:
                return s
        return 0.0


# ═══════════════════════════════════════════════════════════
# 便捷工厂：创建 Qwen3-VL 评判模型函数
# ═══════════════════════════════════════════════════════════

def create_qwen3vl_model_fn(
    base_path: Optional[str] = None,
    lora_path: Optional[str] = None,
    max_new_tokens: int = 256,
    temperature: float = 0.0,
):
    """
    创建 Qwen3-VL 评判模型调用函数。

    使用 inference.py 的加载逻辑，返回一个 callable。

    Args:
        base_path: Qwen3-VL 基座路径
        lora_path: LoRA 适配器路径（可选）
        max_new_tokens: 最大输出 token 数
        temperature: 温度（0.0 = 贪婪解码）

    Returns:
        callable: fn(prompt: str) -> str
    """
    import sys
    import os

    # 确保可以从 lingnao 包导入
    _dir = os.path.dirname(os.path.abspath(__file__))
    if _dir not in sys.path:
        sys.path.insert(0, os.path.dirname(_dir))

    from ..inference import load_model_with_lora
    from ..config import MODEL_PATH as DEFAULT_MODEL_PATH

    model_path = base_path or DEFAULT_MODEL_PATH

    # 使用文本生成（非视觉），不需要 processor 的图像处理
    model, processor = load_model_with_lora(
        base_path=model_path, lora_path=lora_path
    )

    def model_fn(prompt: str) -> str:
        """模型调用函数。"""
        # 构建简单的 ChatML 格式 prompt
        messages = [
            {"role": "system", "content": "你是一个工业指令评测专家。请按指令输出。"},
            {"role": "user", "content": prompt},
        ]
        text = processor.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = processor.tokenizer(text, return_tensors="pt").to(model.device)

        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=(temperature > 0),
            temperature=temperature if temperature > 0 else 1.0,
            pad_token_id=processor.tokenizer.pad_token_id,
        )
        # 只提取生成的部分
        response = processor.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )
        return response.strip()

    return model_fn


# ═══════════════════════════════════════════════════════════
# 更新 eval_matchers 中的占位符
# ═══════════════════════════════════════════════════════════

def _update_matcher_registry():
    """
    将 matchers.BaseMatcher 工厂注册表中的占位 ModelGradedMatcher
    替换为真实实现。在模块首次导入时自动调用。
    """
    from . import matchers as _matchers

    # 替换模块中的占位类
    _matchers.ModelGradedMatcher = ModelGradedMatcher

    # 更新 BaseMatcher.from_config 的注册表（懒加载时动态查找）
    # 因为 registry 是方法内的局部变量，我们直接更新 matchers 模块的符号即可


_update_matcher_registry()
