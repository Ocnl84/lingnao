"""
灵脑 — 统一配置
===============

所有路径、超参、常量集中管理，避免散落在各脚本中。
"""

import os
from dataclasses import dataclass, field
from typing import List

# ─── 路径配置 ───────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# 模型路径（按实际环境改）
MODEL_PATH = os.environ.get(
    "LINGNAO_MODEL_PATH",
    "/root/autodl-tmp/model_cache/qwen/Qwen3-VL-8B-Instruct"
)

# ─── 数据配置 ───────────────────────────────────────────
TRAIN_FILE = os.path.join(DATA_DIR, "train_v2.jsonl")
TEST_FILE = os.path.join(DATA_DIR, "test_v2.jsonl")

# ─── LoRA / QLoRA 超参 ──────────────────────────────────
@dataclass
class LoRAConfig:
    """LoRA 微调配置（与技术方案 5.2/6.2 一致）"""
    r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj"
    ])
    bias: str = "none"
    task_type: str = "CAUSAL_LM"


@dataclass
class TrainingConfig:
    """训练超参（与技术方案 Table 7 一致）"""
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 8       # 等效 batch=16
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    lr_scheduler_type: str = "cosine"
    bf16: bool = True
    logging_steps: int = 5
    save_strategy: str = "epoch"
    save_total_limit: int = 2
    max_seq_length: int = 2048
    optim: str = "paged_adamw_8bit"
    gradient_checkpointing: bool = True


@dataclass
class BitsAndBytesConfig:
    """4bit 量化配置（QLoRA）"""
    load_in_4bit: bool = True
    bnb_4bit_quant_type: str = "nf4"
    bnb_4bit_compute_dtype: str = "bfloat16"
    bnb_4bit_use_double_quant: bool = True


# ─── 评测配置 ───────────────────────────────────────────
# 达标线：100 条测试集平均分 ≥ 0.88
PASS_THRESHOLD = 0.88

# 8 种任务类型（与技术方案 Table 4 一致）
VALID_ACTIONS = [
    "取料_放置",
    "装配",
    "换线",
    "质检",
    "搬运",
    "异常应对",
    "状态查询",
    "协作等待",
]

# 系统提示词
SYSTEM_PROMPT = """你是一个工业机器人指令理解助手。请把工人说的话结合世界状态，输出严格 JSON 格式的结构化指令。

要求：
1. action 必须是以下之一：取料_放置, 装配, 换线, 质检, 搬运, 异常应对, 状态查询, 协作等待
2. 只输出 JSON，不要解释，不要 markdown 代码块
3. 字段值要从世界状态中真实存在的对象/容器引用（id 必须来自 world_state）
4. 必须严格依据工人说的话、世界状态以及看到的图片进行判断，不能自行做出猜想或虚构不存在的信息
5. 模糊词（"那个""轻轻的"）需要结合上下文做合理推断，但推断必须有世界状态或图片中的依据

─── 输出 Schema（按 action 严格遵循）───

取料_放置:
{"action": "取料_放置", "object_filter": {"color": "颜色", "head": "头部类型(可选)"}, "source": "物体id", "target": {"container": "容器id"}, "force": "轻/中/重", "urgency": "常规/紧急"}

装配:
{"action": "装配", "object_filter": {"type": "物体类型"}, "target": {"base": "容器id"}, "force": "轻/中/重", "params": {"torque_nm": 数字, "depth_mm": 数字}}

换线:
{"action": "换线", "line_id": "产线编号", "model": "型号"}

质检:
{"action": "质检", "check_type": "划痕/裂纹/变形/尺寸/毛刺", "object": "物体id", "expected_answer": "有/无"}

搬运:
{"action": "搬运", "object": "物体id", "source": "来源位置", "target_location": "目标位置"}

异常应对:
{"action": "异常应对", "urgency": "紧急/高/中", "response_window_ms": 数字}

状态查询:
{"action": "状态查询", "query": "完成数量/剩余数量/当前速度/总产量"}

协作等待:
{"action": "协作等待", "resume_condition": "人工确认/传感器触发/3秒后自动/上位机指令"}"""


# ─── 目录初始化 ─────────────────────────────────────────
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
