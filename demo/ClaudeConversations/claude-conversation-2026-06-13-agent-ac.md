# Claude Conversation Log

Session ID: agent-ac83cfb5afdc38ead
Date: 2026-06-13 09:51:49

---

## 👤 User

Design a detailed implementation plan for rewriting /root/Brain/demo/lingnao/evaluator.py to follow the OpenAI Evals framework standard. Here is the full context:

## OpenAI Evals Framework (target standard)

### Architecture:
- **YAML config** per eval: `id`, `metrics`, `class`, `args`
- **Class-based**: Each eval is a Python class with `run()` method
- **JSONL dataset**: Each line has `input` (prompt) and `ideal` (expected answer, string or list)
- **Metrics**: `accuracy`, `bootstrap_std`, `f1_score`

### Match Types (Basic/Deterministic):
1. **Match** — `any([b.startswith(a) for b in B])` — strict prefix match
2. **Includes** — `any([(b in a) for b in B])` — expected contained in output  
3. **FuzzyMatch** — `any([(a in b or b in a) for b in B])` — bidirectional containment
4. **JsonMatch** — identical keys/values regardless of order

### Model-Graded (LLM-as-Judge):
- Uses `choice_strings` + `choice_scores` (e.g., {"正确": 1, "部分正确": 0.5, "错误": 0})
- Three strategies: `cot_classify` (reason→answer), `classify_cot` (answer→reason), `classify` (answer only)

### Key metrics:
- `accuracy` = proportion of samples that pass (score >= threshold)
- `bootstrap_std` = bootstrap confidence interval
- `f1_score` = precision/recall on field matching

## Current 灵脑 Evaluator (what needs to change)

File: /root/Brain/demo/lingnao/evaluator.py

Current structure:
- `safe_parse_json()` — 4-tier JSON parse fallback (KEEP)
- `get_nested(obj, path)` — dot-path access (KEEP)
- `score_sample(predicted, expected, criteria)` — weighted scoring: `(must_correct + 0.5*opt_correct) / (n_must + 0.5*n_opt)` (REPLACE with match-type system)
- `evaluate_dataset(predictions, ground_truth)` — returns `{total, avg_score, passed, format_pass_rate, per_sample, per_task_type, errors}` (RESTRUCTURE to OpenAI format)
- `print_report(result)` — terminal output (KEEP but enhance)

### Current eval_criteria format (from data samples):
```json
{
  "must_match": ["action", "object_filter.color", "target.container"],
  "optional": ["object_filter", "source", "target", "force"],
  "match_type": "exact_field_match"
}
```

### Current scoring formula:
```
score = (must_correct + 0.5 × opt_correct) / (n_must + 0.5 × n_opt)
```

WHERE:
- must_correct = count of must_match fields where predicted == expected
- opt_correct = count of optional fields where predicted == expected AND predicted is not None
- denominator = n_must + 0.5 × n_opt

### Files that depend on evaluator:
1. `/root/Brain/demo/run_demo.py` — imports `score_sample`, `evaluate_dataset`, `print_report`
2. `/root/Brain/demo/test_evaluator.py` — unit tests for `safe_parse_json`, `get_nested`, `score_sample`
3. `/root/Brain/demo/lingnao/config.py` — has `PASS_THRESHOLD = 0.88` and `VALID_ACTIONS`

### Dataset format:
Each sample in JSONL has: `id`, `task_type`, `worker_utterance`, `world_state`, `expected_output`, `eval_criteria`

## Design Requirements:
1. Follow OpenAI Evals naming conventions: `accuracy`, `includes`, `fuzzy_match`, `model_graded`
2. Add `bootstrap_std` (bootstrap confidence interval) computation
3. Add `f1_score` metric for field-level precision/recall
4. Create a class-based architecture: `EvalConfig`, `Eval`, `EvalResult`, `SampleResult`
5. Add model-graded eval support (LLM-as-Judge) using Qwen3-VL
6. Add multiple match types: `exact_match`, `json_includes`, `json_fuzzy`, `model_graded`
7. Keep backward compatibility — old function signatures should still work as deprecated wrappers
8. Generate structured JSON report output (not just terminal print)
9. Move eval configuration to `eval_config.yaml` alongside code

## Constraints:
- The existing `must_match`/`optional` weighted scoring is actually GOOD for the domain (safety-critical fields matter more) — should be preserved as ONE match type, not removed
- Don't break run_demo.py or test_evaluator.py
- Keep `safe_parse_json()` and `get_nested()` since they handle real-world JSON parsing edge cases
- The eval_config.yaml should define per-task-type match types and weights

Please produce a detailed implementation plan with:
1. New file structure
2. Class hierarchy
3. Match type implementations
4. Metrics computation (including bootstrap)
5. Backward compatibility strategy
6. Config file schema
7. Migration path for existing code


---

## 🤖 Claude

I'll start by thoroughly exploring the codebase to understand the current implementation, dependencies, and structure.

---

## 🤖 Claude

Let me continue exploring the related files to get the full picture.

---

## 🤖 Claude

Let me examine the data format and other key files.

---

## 🤖 Claude

Let me also check the existing data directory structure and any other relevant patterns.

---

## 🤖 Claude

Now I have a thorough understanding of every file and dependency. Let me produce the detailed implementation plan.

---

## Detailed Implementation Plan: Rewriting evaluator.py to OpenAI Evals Standard

---

### 1. New File Structure

The rewrite introduces 5 new files adjacent to the existing `evaluator.py`, all inside `lingnao/`. No files are deleted; the old `evaluator.py` is refactored in place.

```
lingnao/
  __init__.py                        # UNCHANGED
  config.py                          # MINOR UPDATE: add eval config paths/bootstrap params
  evaluator.py                       # REFACTORED: class-based core + backward compat wrappers (SAME FILE)
  eval_config.yaml                   # NEW: per-task-type eval configuration
  eval_types.py                      # NEW: EvalConfig, EvalResult, SampleResult, MatchResult dataclasses
  eval_matchers.py                   # NEW: BaseMatcher, WeightedFieldMatcher, JsonIncludesMatcher,
                                     #        JsonFuzzyMatcher, ExactMatchMatcher
  eval_metrics.py                    # NEW: compute_accuracy, compute_bootstrap_std, compute_f1_score
  eval_model_graded.py               # NEW: ModelGradedMatcher (LLM-as-Judge via Qwen3-VL)
  data_generator.py                  # UNCHANGED
  inference.py                       # UNCHANGED
  trainer.py                         # UNCHANGED
  data/                              # UNCHANGED
  outputs/                           # UNCHANGED
```

---

### 2. Class Hierarchy and Data Types (in `eval_types.py`)

This file defines all data classes with no logic, keeping them importable by all other modules without circular dependencies.

```python
# eval_types.py

@dataclass
class EvalConfig:
    """Single eval configuration, mirroring OpenAI Evals YAML structure."""
    id: str                              # eval name, e.g. "灵脑_取料_放置"
    metrics: List[str]                   # ["accuracy", "bootstrap_std", "f1_score"]
    match_type: str                      # "weighted_field" | "json_includes" | "json_fuzzy" | "exact" | "model_graded"
    args: Dict[str, Any] = field(default_factory=dict)
    pass_threshold: float = 0.88
    model_graded: Optional['ModelGradedConfig'] = None

@dataclass
class ModelGradedConfig:
    """LLM-as-Judge configuration."""
    model_name: str = "qwen3-vl-8b"
    strategy: str = "classify"           # "classify" | "cot_classify" | "classify_cot"
    choice_strings: List[str] = field(default_factory=lambda: ["正确", "部分正确", "错误"])
    choice_scores: List[float] = field(default_factory=lambda: [1.0, 0.5, 0.0])
    prompt_template: str = ""            # Jinja2-style template with {input}, {ideal}, {completion}
    max_tokens: int = 256
    temperature: float = 0.0

@dataclass
class MatchResult:
    """Result of a single match operation."""
    score: float
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SampleResult:
    """Per-sample evaluation result."""
    id: str
    score: float
    passed: bool
    task_type: str = "unknown"
    parsed_ok: bool = True
    match_details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

@dataclass
class EvalResult:
    """Full evaluation result, corresponding to an EvalConfig run."""
    config_id: str
    total: int
    metrics: Dict[str, float] = field(default_factory=dict)
    samples: List[SampleResult] = field(default_factory=list)
    per_task_type: Dict[str, Dict] = field(default_factory=dict)
    errors: List[Dict] = field(default_factory=list)
    format_pass_rate: float = 0.0
    passed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
```

---

### 3. Match Type Implementations (in `eval_matchers.py`)

All matchers inherit from `BaseMatcher` and implement `match()`.

#### 3a. Abstract Base

```python
class BaseMatcher(ABC):
    match_type: ClassVar[str]

    @abstractmethod
    def match(self, predicted: Any, expected: Any, **kwargs) -> MatchResult:
        """Return a MatchResult with score in [0, 1]."""
        ...

    @classmethod
    def from_config(cls, config: EvalConfig) -> 'BaseMatcher':
        """Factory: instantiate the correct matcher from eval config."""
        registry = {
            "weighted_field": WeightedFieldMatcher,
            "json_includes": JsonIncludesMatcher,
            "json_fuzzy": JsonFuzzyMatcher,
            "exact": ExactMatchMatcher,
            "model_graded": ModelGradedMatcher,
        }
        matcher_cls = registry.get(config.match_type)
        if matcher_cls is None:
            raise ValueError(f"Unknown match_type: {config.match_type}")
        return matcher_cls(**config.args)
```

#### 3b. WeightedFieldMatcher (PRESERVES existing must_match/optional logic)

This is the primary match type for 灵脑 -- it directly maps to the current `score_sample()` algorithm.

```python
class WeightedFieldMatcher(BaseMatcher):
    match_type = "weighted_field"

    def __init__(self, must_match: List[str] = None, optional: List[str] = None,
                 must_weight: float = 1.0, optional_weight: float = 0.5,
                 pass_threshold: float = 0.88):
        self.must_match = must_match or []
        self.optional = optional or []
        self.must_weight = must_weight
        self.optional_weight = optional_weight
        self.pass_threshold = pass_threshold

    def match(self, predicted, expected, **kwargs) -> MatchResult:
        if predicted is None:
            return MatchResult(score=0.0, passed=False)

        n_must = len(self.must_match)
        n_opt = len(self.optional)

        if n_must == 0 and n_opt == 0:
            score = 1.0 if predicted == expected else 0.0
            return MatchResult(score=score, passed=score >= self.pass_threshold)

        must_correct = sum(
            1 for f in self.must_match
            if get_nested(predicted, f) == get_nested(expected, f)
        )
        opt_correct = sum(
            1 for f in self.optional
            if get_nested(predicted, f) == get_nested(expected, f)
            and get_nested(predicted, f) is not None
        )

        denominator = n_must * self.must_weight + n_opt * self.optional_weight
        numerator = must_correct * self.must_weight + opt_correct * self.optional_weight
        score = numerator / denominator if denominator > 0 else 0.0

        return MatchResult(
            score=score,
            passed=score >= self.pass_threshold,
            details={
                "must_correct": must_correct, "n_must": n_must,
                "opt_correct": opt_correct, "n_opt": n_opt,
                "field_results": {...}  # per-field match results
            }
        )
```

#### 3c. JsonIncludesMatcher (mirrors OpenAI "includes")

```python
class JsonIncludesMatcher(BaseMatcher):
    """All expected key-value pairs must be present; extras allowed."""
    match_type = "json_includes"

    def match(self, predicted, expected, **kwargs) -> MatchResult:
        if predicted is None or expected is None:
            return MatchResult(score=0.0, passed=False)

        expected_flat = _flatten_fields(expected)
        predicted_flat = _flatten_fields(predicted)

        matched = sum(
            1 for k, v in expected_flat.items()
            if k in predicted_flat and predicted_flat[k] == v
        )
        total = len(expected_flat)
        score = matched / total if total > 0 else 1.0

        return MatchResult(score=score, passed=score >= self.pass_threshold)
```

#### 3d. JsonFuzzyMatcher (mirrors OpenAI "fuzzy_match")

```python
class JsonFuzzyMatcher(BaseMatcher):
    """Bidirectional containment: a in b OR b in a at the field level."""
    match_type = "json_fuzzy"

    def match(self, predicted, expected, **kwargs) -> MatchResult:
        if predicted is None or expected is None:
            return MatchResult(score=0.0, passed=False)

        expected_flat = _flatten_fields(expected)
        predicted_flat = _flatten_fields(predicted)

        # Count fields where either direction matches
        matched = 0
        total = len(expected_flat)
        for ek, ev in expected_flat.items():
            if ek in predicted_flat:
                pv = predicted_flat[ek]
                if (isinstance(ev, str) and isinstance(pv, str) and (ev in pv or pv in ev)) or ev == pv:
                    matched += 1

        score = matched / total if total > 0 else 1.0
        return MatchResult(score=score, passed=score >= self.pass_threshold)
```

#### 3e. ExactMatchMatcher (mirrors OpenAI "match")

```python
class ExactMatchMatcher(BaseMatcher):
    """Strict equality -- predicted must equal expected exactly."""
    match_type = "exact"

    def match(self, predicted, expected, **kwargs) -> MatchResult:
        if predicted is None:
            return MatchResult(score=0.0, passed=False)
        score = 1.0 if predicted == expected else 0.0
        return MatchResult(score=score, passed=bool(score))
```

#### 3f. ModelGradedMatcher (in `eval_model_graded.py`)

```python
class ModelGradedMatcher(BaseMatcher):
    """
    LLM-as-Judge evaluation using Qwen3-VL.

    Three strategies:
      - classify:       prompt -> answer (choice_string) only
      - cot_classify:   prompt -> reason -> answer extraction
      - classify_cot:   prompt -> answer -> reason extraction
    """
    match_type = "model_graded"

    def __init__(self, choice_strings, choice_scores, strategy="classify",
                 prompt_template=None, model_name="qwen3-vl-8b",
                 model_fn=None, pass_threshold=0.5):
        ...

    def set_model_fn(self, fn):
        """Allow injection of a model callable: fn(prompt) -> str"""
        self._model_fn = fn

    def match(self, predicted, expected, **kwargs) -> MatchResult:
        prompt = self._render_prompt(predicted, expected, kwargs.get("context", {}))
        raw_answer = self._model_fn(prompt)
        choice = self._extract_choice(raw_answer)
        score = self._choice_to_score(choice)
        ...
```

The key design decision for `ModelGradedMatcher`: it accepts a callable `model_fn` rather than loading the model itself. This keeps it decoupled from specific model loading code. `eval_model_graded.py` also provides a convenience `create_model_fn()` that loads Qwen3-VL using the same pattern as `inference.py`.

---

### 4. Metrics Computation (in `eval_metrics.py`)

Each metric function takes a list of `SampleResult` and returns a float.

```python
# eval_metrics.py

import numpy as np

def compute_accuracy(samples: List[SampleResult], threshold: float = 0.88) -> float:
    """Proportion of samples with score >= threshold."""
    if not samples:
        return 0.0
    return sum(1 for s in samples if s.score >= threshold) / len(samples)

def compute_bootstrap_std(scores: List[float], n_bootstrap: int = 1000,
                          ci: float = 0.95) -> Dict[str, float]:
    """
    Bootstrap confidence interval for the mean score.
    Returns {"mean": float, "std": float, "ci_lower": float, "ci_upper": float}.
    """
    if len(scores) < 2:
        return {"mean": np.mean(scores) if scores else 0.0, "std": 0.0,
                "ci_lower": 0.0, "ci_upper": 0.0}
    n = len(scores)
    means = []
    rng = np.random.RandomState(42)  # deterministic seed
    for _ in range(n_bootstrap):
        sample = rng.choice(scores, size=n, replace=True)
        means.append(np.mean(sample))
    alpha = (1 - ci) / 2
    return {
        "mean": float(np.mean(means)),
        "std": float(np.std(means)),
        "ci_lower": float(np.percentile(means, 100 * alpha)),
        "ci_upper": float(np.percentile(means, 100 * (1 - alpha))),
    }

def compute_f1_score(predicted: Dict, expected: Dict) -> float:
    """
    Field-level F1: extract flattened key-value pairs, compute precision/recall.
    This operates on a single sample; aggregate macro-F1 across samples.
    """
    pred_flat = set(_flatten_fields(predicted).items())
    exp_flat = set(_flatten_fields(expected).items())

    tp = len(pred_flat & exp_flat)
    fp = len(pred_flat - exp_flat)
    fn = len(exp_flat - pred_flat)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return f1

def compute_macro_f1(samples_data: List[Tuple[Dict, Dict]]) -> float:
    """Macro-average F1 across all samples."""
    f1s = [compute_f1_score(pred, exp) for pred, exp in samples_data if pred is not None]
    return float(np.mean(f1s)) if f1s else 0.0

def _flatten_fields(obj: Dict, prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dict into dot-path keys. {'a': {'b': 1}} -> {'a.b': 1}"""
    result = {}
    for k, v in obj.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict) and v:
            result.update(_flatten_fields(v, key))
        else:
            result[key] = v
    return result
```

---

### 5. Refactored `evaluator.py` -- In-Place Restructuring

The refactored file has four sections:

**Section A: Utility Functions (unchanged, top of file)**
- `safe_parse_json()` -- unchanged
- `get_nested()` -- unchanged

**Section B: New `Eval` Class (primary interface)**

```python
class Eval:
    """
    Class-based evaluation following OpenAI Evals framework.

    Usage:
        config = EvalConfig.from_yaml("eval_config.yaml", task_type="取料_放置")
        evaluator = Eval(config)
        result = evaluator.run(predictions, ground_truth)
        print(result.to_json(indent=2))
    """

    def __init__(self, config: EvalConfig, matcher: Optional[BaseMatcher] = None):
        self.config = config
        self.matcher = matcher or BaseMatcher.from_config(config)

    def run_sample(self, predicted: Optional[Dict], expected: Dict,
                   eval_criteria: Optional[Dict] = None,
                   context: Optional[Dict] = None) -> SampleResult:
        """Evaluate a single sample against its ground truth."""
        ...

    def run(self, predictions: List[Dict], ground_truth: List[Dict]) -> EvalResult:
        """Run full evaluation over all samples."""
        ...

    @classmethod
    def from_yaml(cls, yaml_path: str, eval_id: Optional[str] = None) -> 'Eval':
        """Factory: create Eval from YAML config file."""
        ...
```

**Section C: Enhanced `print_report()`**

```python
def print_report(result: Union[Dict, EvalResult]):
    """Print terminal report. Also generates structured JSON output."""
    if isinstance(result, EvalResult):
        result = result.to_dict()  # convert to dict for backward compat
    # ... existing print logic ...
    # ADDITION: also writes structured JSON to OUTPUT_DIR/eval_report_<timestamp>.json
```

**Section D: Backward Compatibility Wrappers (bottom of file)**

```python
def score_sample(predicted: Optional[Dict], expected: Dict, criteria: Dict) -> float:
    """
    [DEPRECATED] Kept for backward compatibility with run_demo.py and test_evaluator.py.
    Delegates to WeightedFieldMatcher internally.
    """
    matcher = WeightedFieldMatcher(
        must_match=criteria.get("must_match", []),
        optional=criteria.get("optional", []),
    )
    return matcher.match(predicted, expected).score


def evaluate_dataset(predictions: List[Dict], ground_truth: List[Dict],
                     pass_threshold: float = 0.88) -> Dict:
    """
    [DEPRECATED] Kept for backward compatibility.
    Delegates to Eval internally but returns the old dict format.
    """
    config = EvalConfig(
        id="legacy_dataset_eval",
        metrics=["accuracy", "bootstrap_std"],
        match_type="weighted_field",
        pass_threshold=pass_threshold,
        args={},
    )
    evaluator = Eval(config)
    result = evaluator.run(predictions, ground_truth)
    return _convert_evalresult_to_legacy_dict(result, pass_threshold)
```

The `_convert_evalresult_to_legacy_dict()` function maps the new `EvalResult` back to the exact dictionary structure that `run_demo.py` expects (with keys `total`, `avg_score`, `passed`, `pass_threshold`, `format_pass_rate`, `per_sample`, `per_task_type`, `errors`). This ensures zero breakage for existing callers.

---

### 6. Config File Schema (`eval_config.yaml`)

```yaml
# 灵脑 Evaluation Configuration
# ==============================================================================
# Follows OpenAI Evals framework conventions.
# Loaded by Eval.from_yaml() and used to auto-configure matchers and metrics.

# ─── Global defaults ─────────────────────────────────────────────────────────
defaults:
  metrics: [accuracy, bootstrap_std, f1_score]
  pass_threshold: 0.88
  bootstrap_samples: 1000
  bootstrap_confidence: 0.95

# ─── Match type registry ─────────────────────────────────────────────────────
# Each entry defines a match type available to all task types.
match_types:
  weighted_field:
    description: "Weighted field matching — safety-critical fields weighted higher"
    must_weight: 1.0
    optional_weight: 0.5

  json_includes:
    description: "All expected key-value pairs must be present in prediction"

  json_fuzzy:
    description: "Bidirectional field containment"
    min_similarity: 0.7

  exact:
    description: "Strict full JSON equality"

  model_graded:
    description: "LLM-as-Judge using Qwen3-VL"
    model: qwen3-vl-8b
    strategy: classify
    choice_strings: ["正确", "部分正确", "错误"]
    choice_scores: [1.0, 0.5, 0.0]
    max_tokens: 256
    temperature: 0.0
    prompt_template: |
      你是一个工业机器人指令理解评测专家。请判断模型输出的结构化指令是否与期望输出一致。

      工人说的话：{worker_utterance}
      当前世界状态：{world_state}
      期望的 JSON 输出：{ideal}
      模型实际输出的 JSON：{completion}

      请选择以下评价之一：
      - 正确：模型输出与期望完全一致，所有关键字段都正确
      - 部分正确：主要操作正确，但部分细节字段有偏差
      - 错误：操作类型错误或关键字段严重错误

      只输出评价结果（正确/部分正确/错误），不需要输出其他内容。

# ─── Per-task-type eval configuration ─────────────────────────────────────────
# Each task type specifies: match_type, fields to check, and any override args.
per_task_type:
  取料_放置:
    match_type: weighted_field
    args:
      must_match: [action, object_filter.color, target.container]
      optional: [object_filter, source, target, force, urgency]

  装配:
    match_type: weighted_field
    args:
      must_match: [action, object_filter.type, target.base]
      optional: [force, params.torque_nm, params.depth_mm]

  换线:
    match_type: weighted_field
    args:
      must_match: [action, line_id]
      optional: [model]

  质检:
    match_type: weighted_field
    args:
      must_match: [action, check_type, object]
      optional: [expected_answer]

  搬运:
    match_type: weighted_field
    args:
      must_match: [action, object]
      optional: [source, target_location]

  异常应对:
    match_type: weighted_field
    args:
      must_match: [action, urgency]
      optional: [response_window_ms]

  状态查询:
    match_type: weighted_field
    args:
      must_match: [action, query]
      optional: []

  协作等待:
    match_type: weighted_field
    args:
      must_match: [action, resume_condition]
      optional: []
```

---

### 7. Backward Compatibility Strategy -- Detailed

The critical requirement is that `run_demo.py` and `test_evaluator.py` must continue working without modification. Here is exactly how each import is handled:

| Import in caller | What it currently gets | What it will get after refactor | Broken? |
|---|---|---|---|
| `from lingnao.evaluator import safe_parse_json` | function | same function (unchanged at top of file) | No |
| `from lingnao.evaluator import get_nested` | function | same function (unchanged at top of file) | No |
| `from lingnao.evaluator import score_sample` | function | wrapper that delegates to `WeightedFieldMatcher` | No |
| `from lingnao.evaluator import evaluate_dataset` | function returning dict | wrapper that delegates to `Eval`, returns same dict shape | No |
| `from lingnao.evaluator import print_report` | function | enhanced function, same signature | No |

**The compatibility contract for `evaluate_dataset()` return value** -- `run_demo.py` accesses these keys from the result dict:

```python
result["avg_score"]
result["format_pass_rate"]
result["passed"]
result["total"]
result["per_task_type"]   # dict of {task_type: {avg, count, passed}}
result["errors"]          # list of {id, score, expected, predicted}
```

The wrapper `_convert_evalresult_to_legacy_dict()` must reproduce all these keys exactly.

**The compatibility contract for `score_sample()`** -- `run_demo.py` line 279 and `test_evaluator.py` pass `(predicted_dict, expected_dict, criteria_dict)` and get back a float. The wrapper must produce identical float values for identical inputs. Since `WeightedFieldMatcher` uses the exact same formula, this is guaranteed.

**For `safe_parse_json()` and `get_nested()`** -- they are kept at the top of the file, untouched, with their original function signatures. These are also imported by `inference.py` (`safe_parse_json`) and internal modules.

---

### 8. Updates to `config.py` (Minor)

Three trivial additions:

```python
# Add to config.py alongside existing eval config section:

# Path to eval YAML configuration
EVAL_CONFIG_YAML = os.path.join(BASE_DIR, "eval_config.yaml")

# Bootstrap configuration
BOOTSTRAP_SAMPLES = 1000
BOOTSTRAP_CONFIDENCE = 0.95

# F1 averaging strategy
F1_AVERAGE = "macro"  # "macro" | "micro" | "weighted"
```

---

### 9. Migration Path -- Step-by-Step Implementation Order

**Step 1: Create `eval_types.py`** (no dependencies, pure dataclasses)
- Define `EvalConfig`, `ModelGradedConfig`, `MatchResult`, `SampleResult`, `EvalResult`
- Add `EvalConfig.from_yaml()` classmethod
- Add `EvalResult.to_dict()` and `EvalResult.to_json()` methods
- Define `_flatten_fields()` helper (used across modules)

**Step 2: Create `eval_matchers.py`** (depends on eval_types.py)
- Implement `BaseMatcher` ABC with factory `from_config()`
- Implement `WeightedFieldMatcher` (preserves exact existing formula)
- Implement `JsonIncludesMatcher`
- Implement `JsonFuzzyMatcher`
- Implement `ExactMatchMatcher`
- All matchers import `get_nested` from `evaluator.py` (or we move `get_nested` to `eval_types.py` as a utility)

**Step 3: Create `eval_metrics.py`** (depends on eval_types.py)
- Implement `compute_accuracy()`
- Implement `compute_bootstrap_std()` (with `numpy`, deterministic seed)
- Implement `compute_f1_score()` (single sample)
- Implement `compute_macro_f1()` (aggregated)

**Step 4: Create `eval_model_graded.py`** (depends on eval_types.py, eval_matchers.py)
- Implement `ModelGradedMatcher` with three strategies
- Implement `create_qwen3vl_model_fn()` convenience factory
- Implement answer extraction from raw LLM output (regex-based choice extraction)

**Step 5: Refactor `evaluator.py`** (depends on all above)
- Keep `safe_parse_json()` and `get_nested()` at top (unchanged)
- Add `Eval` class using matchers and metrics modules
- Rewrite `print_report()` to accept both `EvalResult` and legacy dict
- Add `_convert_evalresult_to_legacy_dict()` helper
- Add backward compat wrappers: `score_sample()`, `evaluate_dataset()`
- Update `__main__` CLI to use new `Eval` class
- Ensure `from lingnao.evaluator import *` exports all old + new names

**Step 6: Create `eval_config.yaml`** (no code dependencies)
- Write the YAML file with all 8 task types and their must_match/optional fields
- Define the model_graded prompt template

**Step 7: Update `config.py`** (minor)
- Add `EVAL_CONFIG_YAML`, `BOOTSTRAP_SAMPLES`, `BOOTSTRAP_CONFIDENCE`, `F1_AVERAGE`

**Step 8: Verify backward compatibility**
- Run `python test_evaluator.py` -- must pass all 4 `safe_parse_json` tests, 2 `get_nested` tests, and 4 `score_sample` tests with identical float values
- Run `python run_demo.py --skip-train` (or just the data loading + eval parts) -- must produce the same report structure

**Step 9: Add new tests** (optional enhancement to test_evaluator.py)
- Test `Eval.from_yaml()` loading
- Test `WeightedFieldMatcher` directly (should match old `score_sample` results)
- Test `JsonIncludesMatcher`, `JsonFuzzyMatcher`, `ExactMatchMatcher`
- Test `compute_bootstrap_std` with known scores
- Test `compute_macro_f1` with known predictions
- Test backward compat wrappers produce identical results

---

### 10. Key Design Decisions and Trade-offs

| Decision | Rationale |
|---|---|
| Keep `get_nested()` and `safe_parse_json()` as module-level functions | They are utility functions used by multiple modules (`inference.py`, matchers), not evaluation-specific. Making them methods would create unnecessary coupling. |
| Put backward compat wrappers in same file rather than a separate `compat.py` | Simpler for existing import paths. Avoids confusion about which module is "current." |
| Use `numpy` for bootstrap | Bootstrap requires resampling; implementing manually would be error-prone and slow. `numpy` is already available in the environment (used by transformers/torch). |
| `ModelGradedMatcher` accepts a callable `model_fn` rather than loading the model | Keeps the evaluator decoupled from model loading. The caller (or a factory function) handles model initialization. This also enables testing with mock model functions. |
| YAML config in separate file rather than embedded in code | Follows OpenAI Evals convention. Enables non-developers to adjust eval criteria without touching Python code. |
| `EvalConfig.from_yaml()` allows partial override | Per-task-type configs in YAML merge with defaults, allowing task-specific must_match/optional lists without repeating boilerplate. |
| Preserve `must_match`/`optional` as `weighted_field` match type | The safety-critical field weighting is a domain requirement for industrial robotics. Removing it would be a regression. The weighted field scorer is preserved as a first-class match type, not deprecated. |

---

### 11. Potential Challenges and Mitigations

| Challenge | Mitigation |
|---|---|
| `bootstrap_std` requires `numpy` | Add `numpy` to project dependencies; it is already transitively available via `torch`/`transformers`. Add a graceful import error with fallback. |
| `EvalResult.to_dict()` must match exact legacy dict shape for `run_demo.py` | Write `_convert_evalresult_to_legacy_dict()` with explicit field mapping, and unit-test the output shape against the old `evaluate_dataset()` output format. |
| `ModelGradedMatcher` needs model loaded (heavy) | The matcher is lazy -- it only calls the model function when `match()` is invoked. The factory `create_qwen3vl_model_fn()` is called once and reused across all model-graded samples. |
| YAML config must stay in sync with `VALID_ACTIONS` in `config.py` | Add a validation step in `EvalConfig.from_yaml()` that warns if YAML task types don't match `VALID_ACTIONS`. |
| `test_evaluator.py` asserts exact float values (e.g., `s2` should be 0.8, `s3` should be 0.4) | The wrapper delegates to `WeightedFieldMatcher` which uses the identical formula. The existing assertions will pass unchanged. |

---

### 12. Summary of Changes by File

| File | Action | Lines Changed |
|---|---|---|
| `lingnao/eval_types.py` | CREATE | ~120 lines |
| `lingnao/eval_matchers.py` | CREATE | ~200 lines |
| `lingnao/eval_metrics.py` | CREATE | ~100 lines |
| `lingnao/eval_model_graded.py` | CREATE | ~150 lines |
| `lingnao/eval_config.yaml` | CREATE | ~100 lines |
| `lingnao/evaluator.py` | REFACTOR | ~100 lines added, ~50 lines changed |
| `lingnao/config.py` | MINOR UPDATE | ~10 lines added |
| `test_evaluator.py` | OPTIONAL UPDATE | ~50 lines added (new tests) |
| `run_demo.py` | NO CHANGE | 0 lines |

---

### Critical Files for Implementation
- `/root/Brain/demo/lingnao/evaluator.py` -- Primary refactor target; receives new `Eval` class and backward compat wrappers
- `/root/Brain/demo/lingnao/eval_matchers.py` -- New file; all match type implementations including the preserved `WeightedFieldMatcher`
- `/root/Brain/demo/lingnao/eval_metrics.py` -- New file; bootstrap_std, accuracy, f1_score computation
- `/root/Brain/demo/lingnao/eval_config.yaml` -- New file; YAML-driven eval configuration per task type
- `/root/Brain/demo/run_demo.py` -- Must not break; validates backward compatibility of all wrapper functions

---

