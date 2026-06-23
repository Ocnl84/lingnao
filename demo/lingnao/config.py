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
TRAIN_FILE = os.path.join(DATA_DIR, "PRJ-01_lingnao_high_generalization_1056.jsonl")
TEST_FILE = os.path.join(DATA_DIR, "PRJ-01_lingnao_test_100.jsonl")

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
# 达标线：100 条测试集平均分 ≥ 0.88（OpenAI Evals: accuracy ≥ threshold）
PASS_THRESHOLD = 0.88

# Eval YAML 配置文件路径
EVAL_CONFIG_YAML = os.path.join(BASE_DIR, "eval", "config.yaml")

# Bootstrap 置信区间参数（OpenAI Evals 标准）
BOOTSTRAP_SAMPLES = 1000
BOOTSTRAP_CONFIDENCE = 0.95

# F1 平均策略
F1_AVERAGE = "macro"  # macro | micro | weighted

# 8 种任务类型（与技术方案 Table 4 一致）
VALID_ACTIONS = [
    "取料放置",
    "装配",
    "换线",
    "质检",
    "搬运",
    "异常应对",
    "状态查询",
    "协作等待",
]

# 系统提示词
SYSTEM_PROMPT = """你是一个工业机器人指令理解助手。请根据工人说的话，输出严格 JSON 格式的结构化指令。

要求：
1. action 必须是以下之一：取料放置, 装配, 换线, 质检, 搬运, 异常应对, 状态查询, 协作等待
2. 只输出 JSON，不要解释，不要 markdown 代码块
3. 字段值必须从工人话语中提取，不得虚构
4. 模糊表述（"那个""轻轻""死劲"）需结合语境合理推断，但推断必须有依据

─── 输出 Schema（按 action 严格遵循）───

取料放置:
{"action": "取料放置", "object_filter": {"color": "物体颜色", "type": "物体类型"}, "target_container": "目标容器名", "force": "力度描述(轻/重/正常/轻轻地/死劲/大力/温柔/减力/加码/稍轻)", "urgency": "高/低"}

装配:
{"action": "装配", "object": "物体类型(如销轴/螺母/齿轮/法兰等)", "base": "安装底座名(如卡盘/工作台/支撑柱/5号夹具等)", "force": "轻/重/正常", "torque": "扭矩值(如0.4N·m)"}

换线:
{"action": "换线", "line_number": "产线编号(如3号线/B侧4线/C流水线等)", "model": "产品型号(如C-200/S-600/T-800等)"}

质检:
{"action": "质检", "inspection_type": "检查类型(毛刺/表面划痕/锈蚀/气孔/飞边/污渍/尺寸超差/形变/喷漆颜色或色差/焊点虚焊/缺角/孔位偏离/松动/裂纹/镀层剥落)", "object": "被检物体类型(如轴承/支架/核心板/接头/阀门等)", "expected_answer": "期望结果(无/合格/颜色均匀/饱满/无气孔/无毛刺/未变形/干净/精准/无剥落/无锈斑/完整/顺滑/牢固/无划痕)"}

搬运:
{"action": "搬运", "object": "物体类型名", "source_location": "来源位置(如二号工作台/红框/1号流水线/A仓/缓存区等)", "target_location": "目标位置(如暂存转运区/4号收料箱/B区传送带/质检台/烘干线等)"}

异常应对:
{"action": "异常应对", "urgency": "紧急程度(最高级别紧急/高/中/低)", "time_window": "响应时间窗口(如1000ms/2000ms/3000ms/5000ms/10000ms/60000ms/120000ms等)"}

状态查询:
{"action": "状态查询", "query_content": "查询内容(工作台温度/剩余物料数量/历史故障状态/系统主气压值/当日合格品总数/目标剩余订单量/装配良率/当前设备运行功率/当前班次信息/下阶段排产计划/产线节拍速度/设备运行时间/炉区实时温度/当前生产元件计数或第几个)"}

协作等待:
{"action": "协作等待", "resume_condition": "恢复条件(如小车通过或交通管制解除/收到到位信号/光电传感器绿灯亮/上模具回缩到位/真空压力达标/箱子装满或收到满箱信号/机械臂归位安全信号/机械臂离开复位/条码扫描成功信号/气路残压排空/设备复位完成/固化时间结束/上游物料到达传感器/岗位交接班人员到位)"}"""


# ─── 目录初始化 ─────────────────────────────────────────
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
