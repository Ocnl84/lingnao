"""
灵脑 — 训练/测试数据生成器
============================

按技术方案第四节格式生成工业指令数据集。
支持手写模板 + LLM 合成扩充。

每条样本包含:
  - worker_utterance: 工人自然语言
  - world_state: 场景对象/容器
  - expected_output: 结构化 JSON
  - eval_criteria: 评测规则

v2 改进：
  - 大幅扩充话术模板（每种任务 15-25 条）
  - 内置去重：生成时追踪已出现的话术，重复则重试
  - 修复模板兼容性过滤过于严格导致话术坍缩的问题
"""

import json
import random
import os
import sys
from typing import Dict, List, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import TRAIN_FILE, TEST_FILE, VALID_ACTIONS

# ═══════════════════════════════════════════════════════════
# 模板库
# ═══════════════════════════════════════════════════════════

# 常见物体
OBJECTS = [
    {"type": "螺丝", "variants": [
        {"color": "蓝色", "head": "十字", "material": "钢"},
        {"color": "红色", "head": "一字", "material": "钢"},
        {"color": "黑色", "head": "内六角", "material": "不锈钢"},
        {"color": "银色", "head": "十字", "material": "铝"},
    ]},
    {"type": "螺母", "variants": [
        {"color": "银色", "spec": "M3"},
        {"color": "金色", "spec": "M4"},
        {"color": "黑色", "spec": "M5"},
    ]},
    {"type": "轴承", "variants": [
        {"color": "银色", "size": "小型"},
        {"color": "黑色", "size": "中型"},
    ]},
    {"type": "齿轮", "variants": [
        {"color": "银色", "teeth": 24},
        {"color": "黑色", "teeth": 36},
    ]},
    {"type": "外壳", "variants": [
        {"color": "白色", "material": "塑料"},
        {"color": "灰色", "material": "金属"},
    ]},
    {"type": "电路板", "variants": [
        {"color": "绿色", "status": "正常"},
        {"color": "绿色", "status": "有划痕"},
    ]},
]

CONTAINERS = [
    {"type": "料盒", "positions": ["左一", "左二", "右一", "右二"]},
    {"type": "工位", "positions": ["工位1", "工位2", "工位3", "工位4"]},
    {"type": "传送带", "positions": ["A区", "B区", "C区"]},
    {"type": "NG区", "positions": ["NG区"]},
    {"type": "打磨台", "positions": ["打磨台"]},
]

# 8 种任务类型的 utterance 模板 —— 大幅扩充，避免话术坍缩
TASK_TEMPLATES = {
    "取料_放置": {
        "utterances": [
            # 原始 5 条
            "把那个{color}{head}的{type}放到{container}里",
            "把{color}的{type}从{src}拿到{dst}",
            "把那堆{type}里{color}的挑出来，放{dst}上",
            "把那个带{head}头的{color}{type}轻轻放到{container}",
            "从{src}取出{color}{type}，摆到{dst}",
            # 新增 (v2)
            "来，{color}{type}抓起来，搁{dst}",
            "{src}里头{color}的{type}，帮我拿到{dst}",
            "看见没，{color}那个{type}，放{container}那边去",
            "把{color}{type}拣出来，送到{container}",
            "赶紧的，从{src}拿个{color}{type}过来，放{dst}",
            "来来来，{color}那个{type}，丢{dst}去",
            "手边{src}里头有个{color}{type}，弄到{dst}",
            "把那个带{head}的{color}{type}抓了，搁{container}里",
            "小心里面那个{color}{type}啊，从{src}掏出来放{dst}",
            "{dst}那边缺个{color}{type}，从{src}拿一个补上",
            "把那堆{color}的{type}从{src}挑出来，送到{container}",
            "帮我抓个{color}{type}，{head}头的那个，搁{dst}上头",
            "那个{color}{type}，对就它，帮我放到{container}",
            # v3 扩充 (30+)
            "哎，{color}那个{type}，{head}头的，从{src}拿过来放{dst}",
            "{src}里面翻一下，有个带{head}的{color}{type}，拿出来搁{container}",
            "你瞅瞅{src}，把那{color}{type}拎到{dst}去",
            "看着点啊，{color}的{type}，{head}的那种，从{src}搞到{container}",
            "轻拿轻放，{color}{type}从{src}取到{dst}，别磕了",
            "下一个活：从{src}把{color}{type}取出来，送到{container}",
            "这个{color}{type}不在这堆里，去{src}找，放{container}",
            "抓{color}的{type}，别拿错了，要{head}头的，放{dst}",
            "{color}{type}，{head}的，从{src}挑，放{container}就行",
            "听好：{src}→{color}{type}→{head}头→{dst}，走",
            "上料了，{color}的{type}从{src}拿，搁{container}去",
            "{src}那有个{color}的{type}，看到了吧，拿到{container}",
            "来活了，{color}{type}一颗，{head}的，从{src}到{container}",
            "拣料，要{color}的{type}，{head}头，放{dst}，轻拿",
        ],
        "fields": ["action", "object_filter", "source", "target", "force"],
        "must_match": ["action", "object_filter.color", "target.container"],
    },
    "装配": {
        "utterances": [
            # 原始 4 条
            "把{part}装到{base}上",
            "把{part}拧紧到{base}上，扭矩{t}N·m",
            "把{part}对准{base}压进去，深度{d}mm",
            "先把{part1}放{base}上，再把{part2}拧上去",
            # 新增 (v2)
            "{part}装上{base}，拧紧啊",
            "来，把这{part}给我拧{base}上去，扭矩{t}牛",
            "对准{base}，把{part}压进去，深度{d}毫米",
            "{base}缺口一个{part}，补上，扭矩{t}",
            "这个{part}和那个{part2}，全装{base}上",
            "来来来{part}拿一个，装{base}上，别拧太紧，{t}牛够了",
            "先放垫片，再拧{part}，都在{base}上搞",
            "{part}装{base}，深度{d}，打完收工",
            "把{part}扣{base}上，打{t}N·m的扭矩",
            "把那{part}装{base}上去，扭矩调到{t}",
            "把{part}压到{base}里，深度{d}mm，别歪了",
            "先把卡簧放上，再把{part}拧{base}上",
            # v3 扩充 (30+)
            "装配件来了：把{part}对好{base}，拧进去，{t}N·m",
            "{part}还没装呢，赶紧拧{base}上，扭矩{t}",
            "这个{part}用{head}头拧，装在{base}上，打{t}牛",
            "来，{part}＋{part2}，一套装{base}上，{t}N·m",
            "下一道：{part}压入{base}，深度{d}mm，不能偏",
            "先把{base}清理一下，然后{part}装上去，扭矩{t}",
            "手里{part}拿来，装{base}上，深度{d}mm，扭力{t}",
            "装{part}，对准{base}的孔，{t}N·m，别滑牙",
            "把{part}装到{base}上，先预拧再打扭矩，{t}N·m",
            "那{part}给我装{base}去，压深{d}mm，扭矩{t}牛",
            "{part}装好没？装{base}上，扭矩{t}，深度{d}",
            "上好{part}，锁{base}，扭矩{t}N·m，检查一下",
            "别磨蹭，{part}拿过来装{base}，{t}牛，{d}mm深",
            "精装{part}到{base}，扭矩{t}N·m，深度{d}mm，公差±0.1",
        ],
        "fields": ["action", "object_filter", "target", "force", "params"],
        "must_match": ["action", "object_filter.type", "target.base"],
    },
    "换线": {
        "utterances": [
            # 原始 4 条
            "切到{line}号产线",
            "换线，切到型号{model}",
            "不做了，切回{line}号线",
            "准备切换到{line}号线，{model}型号",
            # 新增 (v2)
            "换线换线，{line}号，搞{model}的",
            "这条线不跑了，切{line}号继续",
            "给我切{line}号线，上{model}型号",
            "不搞这个了，切{line}号线去",
            "切，换{line}号线",
            "改{line}号线，上{model}",
            "不做了不做了，切回{line}号线",
            "停一下，先切到{line}号，型号{model}",
            "换线，{line}号，型号{model}，准备",
            "切产线，{line}号，{model}的活",
            "给我换{line}号线，跑{model}",
            # v3 扩充 (25+)
            "线换了没？切{line}号，做{model}",
            "快换线，{line}号线，{model}型号，立刻",
            "这条线清掉了，切{line}号，上{model}的料",
            "通知换线：{line}号线，产品{model}，现在就切",
            "来来来，换线，{line}号，型号{model}，麻利点",
            "别在这条线耗了，切{line}号线搞{model}",
            "下一批{model}，切到{line}号线上去",
            "换线指令：目标{line}号线，型号{model}，确认切换",
            "产线切换，{line}号，{model}，老规矩",
            "这条线收工了，切{line}号继续干{model}",
	        ],
        "fields": ["action", "line_id", "model"],
        "must_match": ["action", "line_id"],
    },
    "质检": {
        "utterances": [
            # 原始 5 条
            "看下{obj}有没有{defect}",
            "检查{obj}表面有没有{defect}",
            "检查{obj}的{attr}，不合格就放NG区",
            "这批{obj}全检一遍{defect}",
            "看看{obj}有没有{defect}，有的话放NG区",
            # 新增 (v2)
            "过一遍{obj}，查下{defect}",
            "这批{obj}挨个查{defect}，有问题的挑出来",
            "来，检查下{obj}，主要看{defect}",
            "{obj}有没有{defect}，仔细查，别漏了",
            "先别装，这批{obj}过一遍{defect}",
            "帮我看一眼{obj}，{defect}没",
            "这批{obj}全检{defect}，有问题直接扔NG区",
            "瞅一眼这个{obj}，看有没有{defect}",
            "{obj}查一下{defect}，快点",
            "挨个查，这批{obj}，主要看有没有{defect}",
            # v3 扩充 (25+)
            "外检来一下：这批{obj}查{defect}，全检",
            "验货了，{obj}一个一个过，查{defect}和{attr}",
            "{obj}抽检{defect}，每箱抽5个，严一点",
            "品质这边：{obj}查{defect}，关键件别放过",
            "先停一下产，{obj}拉出来过一遍{defect}",
            "目检{obj}，看{defect}，{attr}也看下",
            "把关了：{obj}过{defect}检查，不合格的筛出来",
            "这箱{obj}掀开，查{defect}，一个一个翻",
            "{obj}做好没？先看看{defect}再流下去",
            "上线前确认：{obj}有没有{defect}，查清楚",
        ],
        "fields": ["action", "check_type", "object", "expected_answer"],
        "must_match": ["action", "check_type", "expected_answer"],
    },
    "搬运": {
        "utterances": [
            # 原始 4 条
            "把这箱{obj}搬到{loc}",
            "把{obj}从{src}搬到{dst}",
            "把整个料盘搬到{loc}",
            "把{src}的{obj}全搬到{dst}",
            # 新增 (v2)
            "这堆{obj}别放{src}了，搬{dst}去",
            "{obj}在{src}放太久了，清一下，搬{dst}",
            "来，把{src}的{obj}全拖{dst}",
            "清{src}，{obj}全挪到{dst}",
            "整盘{obj}拉走，从{src}到{dst}",
            "{obj}换地方了，{src}→{dst}，搬",
            "来个人...哦不，你自己来，把这{obj}弄{dst}去",
            "这箱{obj}，搬{dst}去",
            "把{obj}从{src}搞到{dst}，快点",
            "这堆{obj}别放{src}了，搬{dst}去",
            # v3 扩充 (25+)
            "物流：{obj}从{src}转到{dst}，整箱搬",
            "{src}堆满了，{obj}清走，搬到{dst}",
            "{obj}挪个窝，{src}→{dst}，现在就搬",
            "腾地方了，{src}的{obj}全部拉{dst}",
            "这托{obj}太重，小心点，从{src}叉到{dst}",
            "倒库：{obj}从{src}搬到{dst}，整托移",
            "{obj}别堆{src}了，拉走，目标{dst}",
            "清场，{src}上面{obj}全搬{dst}，一件不留",
            "来活了，{obj}一箱，{src}搬到{dst}，注意别翻",
            "那堆{obj}碍事，从{src}清到{dst}，现在就搞",
            "把{src}里的{obj}倒到{dst}，快点清完",
        ],
        "fields": ["action", "object", "target_location"],
        "must_match": ["action", "target_location"],
    },
    "异常应对": {
        "utterances": [
            # ── 紧急 ──
            "{obj}要掉了！接住",
            "急停！{reason}",
            "掉了！{obj}掉地上了",
            "卧槽！{obj}要掉了，快接住",
            "快停！{obj}掉了！",
            "别动了别动了，{obj}卡住了，停机",
            "紧急停止！{obj}飞出来了",
            "停停停！{reason}，急停",
            "快拍急停！{obj}砸下来了！",
            "撞了！{obj}要撞上了，紧急制动！",
            # ── 高 ──
            "零件卡住了，暂停",
            "有异响，快停下看看",
            "有异响有异响，快停下看看",
            "{obj}卡死了，急停",
            "{obj}卡住了，先停机检查",
            "不对劲，{obj}那有异响，停一下",
            "卡住了卡住了，{obj}动不了，停机",
            "听着不对，{obj}那边咔咔响，快停",
            "{obj}抖得厉害，停机查一下",
            "震了震了，{obj}在跳，快停",
            "温度高了，{obj}发烫，停机冷却",
            # ── 中 ──
            "供料异常，先暂停",
            "供料断了供料断了，先停了再说",
            "供料跟不上，停一下等等料",
            "供料口堵了，暂停清理下",
            "料供不上了，先停",
            "供料有点问题，停一下看看",
            "供料不稳，暂停，检查一下",
            "料快没了，先停，等我叫补料",
            "切料不顺，暂停调整",
            "供料那头卡了一下，停3秒缓缓",
            "供料节奏不对，暂停重设",
            "气压掉了，供料推不动，先停",
            "料架歪了，暂停调整一下再走",
            "轨道上有杂物，清一下再继续",
        ],
        "fields": ["action", "urgency", "response_window_ms"],
        "must_match": ["action", "urgency"],
    },
    "状态查询": {
        "utterances": [
            # ── 完成数量 ──
            "现在做到第几个了",
            "这波{obj}做了多少了",
            "生产了多少{obj}，报一下",
            "报一下现在的产量",
            "做了几个{obj}了，数数",
            "这批次{obj}做多少了",
            "出来没，{obj}做完几个了",
            "给我个数，{obj}做多少个了",
            # ── 剩余数量 ──
            "还剩多少个{obj}",
            "还剩几个{obj}，够不够",
            "还有几个{obj}没做",
            "{obj}还剩多少，够这批吗",
            "看看{obj}库存还剩几个",
            "差多少{obj}，报一下",
            "还缺几个{obj}，算一下",
            # ── 当前速度 ──
            "当前产线速度多少",
            "速度多少，现在",
            "产线速度现在多少",
            "看一下现在节拍是多少",
            "线速多少，报一下",
            "现在跑多快，产线速度",
            "节拍多少秒一个，现在",
            "效率怎么样，现在的节拍",
            # ── 总产量 ──
            "报一下今天的总产量",
            "今天产了多少，总共",
            "今天一共做了多少件",
            "总产出多少个了，报数",
            "今天累计做了多少{obj}",
            "汇总一下，今天总产量",
            "从上班到现在做了多少了",
            "今天产量达标没，报个数",
        ],
        "fields": ["action", "query"],
        "must_match": ["action", "query"],
    },
    "协作等待": {
        "utterances": [
            # ── 人工确认 (14 条) ──
            "等一下，我还没走开",
            "先停一下，等我确认完",
            "先别急，等人来了再开",
            "等一下等一下，我还没走开",
            "等等，我检查完再开",
            "先别动，我过来看一下",
            "停一下，等我确认OK再继续",
            "我还没退到安全区，先别动",
            "等会儿，我检查下夹具",
            "手里有{obj}，等我放好了再开",
            "先别动{obj}，我人还在旁边呢",
            "等我退远点，{obj}那儿我去看一眼",
            "等一下，{obj}这儿有点问题我看下",
            "别急着开，我先看看{obj}装好没",
            # ── 传感器触发 (13 条) ──
            "别动啊，等传感器信号",
            "等{signal}信号再继续",
            "等会儿，{signal}触发再继续",
            "传感器还没触发，等着别动",
            "等{signal}到位了再走",
            "{signal}没亮呢，等着",
            "别急着走，{signal}确认了再说",
            "{obj}的{signal}还没到位，等着",
            "等{signal}给信号，{obj}那边确认了再走",
            "{signal}信号没来，不许动{obj}",
            "传感器还没触发{obj}，别抓",
            "等{obj}那头的{signal}确认好",
            "触发{signal}再抓{obj}，别抢跑",
            # ── 3秒后自动 (12 条) ──
            "停 3 秒再继续",
            "先别动，等3秒再继续",
            "停3秒，然后自己走",
            "休息3秒，自动续",
            "等3秒，让它自己恢复",
            "停一下，3秒后自动走",
            "缓3秒啊，别急着动",
            "搞完{obj}，停3秒再走",
            "碰一下{obj}，等3秒，继续",
            "{obj}挪完停3秒，然后再抓下一个",
            "干完这步停3秒，等{obj}稳了再动",
            "每做完一个{obj}缓3秒，别连着来",
            # ── 上位机指令 (13 条) ──
            "等上位机发指令，别自己动啊",
            "停了，等上位机指令",
            "等上位机信号再继续",
            "没有上位机指令不许动",
            "先挂起，等上位机下发指令",
            "等上位机说继续再继续",
            "上位机还没回复，等着",
            "等上位机给绿灯了再走",
            "挂起了，等上位机发下一个指令",
            "上位机不下指令，{obj}这边不能动",
            "盯着上位机，{obj}的指令到了再走",
            "没有上位机指令，{obj}一个也别碰",
            "{obj}的任务挂起了，等上位机确认",
        ],
        "fields": ["action", "resume_condition"],
        "must_match": ["action", "resume_condition"],
    },
}


def random_object() -> Dict:
    """随机生成一个物体"""
    t = random.choice(OBJECTS)
    v = random.choice(t["variants"])
    obj_id = f"obj_{random.randint(100, 999)}"
    return {"id": obj_id, "type": t["type"], **v, "location": random.choice(["箱子A", "箱子B", "料盘1", "料盘2", "托盘"])}


def random_container() -> Dict:
    """随机生成一个容器"""
    t = random.choice(CONTAINERS)
    pos = random.choice(t["positions"])
    cid = f"box_{random.randint(100, 999)}"
    return {"id": cid, "type": t["type"], "position": pos, "capacity": random.randint(5, 20)}


def build_world_state(objects: List[Dict], containers: List[Dict]) -> Dict:
    """构建世界状态"""
    return {
        "objects": objects,
        "containers": containers,
    }


def fill_template(template: str, context: Dict) -> str:
    """填充模板变量，缺失的用随机值"""
    result = template
    for k, v in context.items():
        result = result.replace("{" + k + "}", str(v))
    # 替换残留占位符
    import re
    placeholders = set(re.findall(r"\{(\w+)\}", result))
    defaults = {
        "color": random.choice(["蓝色", "红色", "黑色", "银色", "白色"]),
        "head": random.choice(["十字", "一字", "内六角"]),
        "type": random.choice(["螺丝", "螺母", "齿轮", "轴承"]),
        "container": random.choice(["左边第二个盒子", "工位2", "A区", "右边料盒"]),
        "src": random.choice(["箱子A", "料盘1", "料盒B"]),
        "dst": random.choice(["工位1", "工位3", "传送带B", "装配台"]),
        "loc": random.choice(["A区传送带", "B区", "工位4"]),
        "part": random.choice(["螺母", "齿轮", "外壳"]),
        "base": random.choice(["底座", "轴", "框架"]),
        "part1": random.choice(["垫片", "弹簧"]),
        "part2": random.choice(["螺丝", "螺母"]),
        "t": random.choice(["0.5", "0.8", "1.2"]),
        "d": random.choice(["5", "10", "15"]),
        "line": random.choice(["2", "3", "4"]),
        "model": random.choice(["A-200", "B-500", "C-1000"]),
        "obj": random.choice(["零件", "螺丝", "外壳", "电路板"]),
        "defect": random.choice(["裂纹", "划痕", "变形", "毛刺"]),
        "attr": random.choice(["尺寸", "表面", "硬度"]),
        "reason": random.choice(["卡住了", "供料断了", "需要换刀"]),
        "signal": random.choice(["光电传感器", "按钮确认", "上位机"]),
    }
    for ph in placeholders:
        if ph in defaults:
            result = result.replace("{" + ph + "}", str(defaults[ph]))
    return result


def _build_utterance_context(
    task_type: str,
    expected: Dict,
    objects: List[Dict],
    containers: List[Dict],
) -> Dict:
    """
    从 expected_output + 世界状态反向构建 utterance 模板上下文。

    确保 utterance 中提及的值与 expected_output 严格一致。
    """
    obj = objects[0] if objects else {}
    container = containers[0] if containers else {}

    ctx = {
        "color": obj.get("color", ""),
        "head": obj.get("head", ""),
        "type": obj.get("type", ""),
        "obj": obj.get("type", "零件"),
        "src": obj.get("location", ""),
    }
    if containers:
        ctx["dst"] = container.get("position", "")
        ctx["container"] = container.get("position", "")
        ctx["loc"] = container.get("position", "")

    # ── 从 expected_output 反向填充任务特定占位符 ──
    if task_type == "质检":
        ctx["defect"] = expected.get("check_type", "")
        ctx["attr"] = expected.get("check_type", "")
        ctx["obj"] = obj.get("type", "零件")
    elif task_type == "换线":
        ctx["line"] = expected.get("line_id", "")
        ctx["model"] = expected.get("model", "")
    elif task_type == "装配":
        ctx["part"] = obj.get("type", "")
        ctx["part1"] = random.choice(["垫片", "弹簧"])
        # part2 优先使用 world_state 中第二个物体的类型，确保话术与场景一致
        if len(objects) > 1:
            ctx["part2"] = objects[1].get("type", "螺丝")
        else:
            # 选一个与 part 不同的常见零件类型
            other_parts = [p for p in ["螺丝", "螺母", "轴承", "齿轮"] if p != obj.get("type")]
            ctx["part2"] = random.choice(other_parts) if other_parts else "螺丝"
        params = expected.get("params", {})
        ctx["t"] = str(params.get("torque_nm", "0.8"))
        ctx["d"] = str(params.get("depth_mm", "10"))
        ctx["base"] = container.get("position", "工位1")
    elif task_type == "异常应对":
        ctx["obj"] = obj.get("type", "零件")
        ctx["reason"] = random.choice(["卡住了", "供料断了", "需要换刀", "飞出来了"])
    elif task_type == "状态查询":
        ctx["obj"] = obj.get("type", "零件")
    elif task_type == "协作等待":
        resume = expected.get("resume_condition", "")
        if resume == "上位机指令":
            ctx["signal"] = "上位机"
            ctx["reason"] = "需要换刀"
        elif resume == "传感器触发":
            ctx["signal"] = random.choice(["光电传感器", "按钮确认"])
            ctx["reason"] = "需要换刀"
        elif resume == "3秒后自动":
            ctx["reason"] = "需要换刀"
        else:  # 人工确认
            ctx["reason"] = "卡住了"
            ctx["signal"] = "光电传感器"

    return ctx


# ─── 模板兼容性映射：expected_output 值 → 模板中出现的特征词 ───
# 用于过滤出与 expected_output 一致的 utterance 模板
TEMPLATE_COMPAT = {
    "状态查询": {
        "完成数量": ["做到第几", "做了多少", "产量", "生产了多少", "做了几个", "做多少"],
        "剩余数量": ["还剩多少", "还剩几个", "库存还剩", "够不够", "还有几个"],
        "当前速度": ["速度", "节拍", "跑多快", "线速"],
        "总产量": ["总产量", "今天产了", "一共做了", "总产出"],
    },
    "协作等待": {
        "人工确认": ["等一下", "先停一下", "先别急", "等我", "等等", "先别动，我过来", "停一下，等我",
                      "手里有", "我人还在", "我去看", "我看下", "我检查", "别急着开"],
        "传感器触发": ["等{signal}信号", "传感器信号", "等会儿", "传感器还没", "传感器触发",
                       "还没到位", "给信号", "信号没来", "确认好", "别抢跑"],
        "3秒后自动": ["3 秒", "3秒", "休息3秒", "等3秒", "停3秒", "缓3秒",
                      "搞完", "碰一下", "挪完", "干完这步", "每做完"],
        "上位机指令": ["上位机发指令", "上位机指令", "上位机信号", "上位机说",
                       "不下指令", "盯着上位机", "任务挂起"],
    },
    "异常应对": {
        "紧急": ["急停", "掉了", "快停下", "接住", "卧槽", "快停", "别动", "紧急停止", "停停停"],
        "高": ["卡住了", "异响", "卡死", "停机检查", "不对劲", "卡住", "咔咔响", "听着不对"],
        "中": ["供料", "先暂停", "停一下等等", "料供不上", "料快没", "切料", "料跟不上"],
    },
}


def _filter_compatible_templates(task_type: str, expected: Dict, templates: List[str]) -> List[str]:
    """过滤出与 expected_output 兼容的 utterance 模板。"""
    compat = TEMPLATE_COMPAT.get(task_type, {})
    if not compat:
        return templates

    if task_type == "状态查询":
        query = expected.get("query", "")
        features = compat.get(query, [])
        compatible = [t for t in templates if any(f in t for f in features)]
        return compatible if compatible else templates

    elif task_type == "协作等待":
        cond = expected.get("resume_condition", "")
        features = compat.get(cond, [])
        compatible = [t for t in templates if any(f in t for f in features)]
        return compatible if compatible else templates

    elif task_type == "异常应对":
        urgency = expected.get("urgency", "")
        features = compat.get(urgency, [])
        compatible = [t for t in templates if any(f in t for f in features)]
        return compatible if compatible else templates

    else:
        return templates


def _build_expected_output(task_type: str, objects: List[Dict], containers: List[Dict]) -> Dict:
    """根据任务类型构建 expected_output"""
    obj = objects[0] if objects else {"id": "obj_001", "type": "螺丝", "color": "蓝色"}
    container = containers[0] if containers else {"id": "box_001", "position": "左二"}

    base = {"action": task_type}

    if task_type == "取料_放置":
        obj_filter = {"color": obj.get("color", "")}
        if obj.get("head"):
            obj_filter["head"] = obj.get("head")
        base.update({
            "object_filter": obj_filter,
            "source": obj.get("id", "obj_001"),
            "target": {"container": container.get("id", "box_001")},
            "force": random.choice(["轻", "中", "重"]),
            "urgency": "常规",
        })
    elif task_type == "装配":
        base.update({
            "object_filter": {"type": obj.get("type", "")},
            "target": {"base": container.get("id", "box_001")},
            "force": "中",
            "params": {"torque_nm": random.choice([0.5, 0.8, 1.0, 1.2]), "depth_mm": random.choice([5, 8, 10, 12, 15])},
        })
    elif task_type == "换线":
        base.update({
            "line_id": str(random.choice([2, 3, 4, 5])),
            "model": random.choice(["A-200", "B-500", "C-1000"]),
        })
    elif task_type == "质检":
        check = random.choice(["划痕", "裂纹", "变形", "尺寸", "毛刺"])
        base.update({
            "check_type": check,
            "object": obj.get("id", "obj_001"),
            "expected_answer": random.choice(["有", "无"]),
        })
    elif task_type == "搬运":
        base.update({
            "object": obj.get("id", "obj_001"),
            "source": obj.get("location", "箱子A"),
            "target_location": container.get("position", "A区传送带"),
        })
    elif task_type == "异常应对":
        urgency = random.choice(["紧急", "高", "中"])
        response_map = {"紧急": [200, 500], "高": [500, 800, 1000], "中": [500, 800, 1000, 1500]}
        base.update({
            "urgency": urgency,
            "response_window_ms": random.choice(response_map[urgency]),
        })
    elif task_type == "状态查询":
        base.update({
            "query": random.choice(["完成数量", "剩余数量", "当前速度", "总产量"]),
        })
    elif task_type == "协作等待":
        base.update({
            "resume_condition": random.choice(["人工确认", "传感器触发", "3秒后自动", "上位机指令"]),
        })

    return base


def generate_sample(
    task_type: str,
    sample_id: str,
    objects: Optional[List[Dict]] = None,
    containers: Optional[List[Dict]] = None,
) -> Dict:
    """
    生成一条训练/测试样本。

    与技术方案 4.1 的 JSON schema 完全对齐。

    关键：先构建 expected_output，再从 expected_output 反向生成 utterance，
    确保两者严格一致。
    """
    if task_type not in TASK_TEMPLATES:
        raise ValueError(f"未知任务类型: {task_type}，有效值: {list(TASK_TEMPLATES.keys())}")

    tpl = TASK_TEMPLATES[task_type]

    # 1. 随机生成世界状态
    if objects is None:
        objects = [random_object() for _ in range(random.randint(1, 2))]
    if containers is None:
        containers = [random_container() for _ in range(random.randint(1, 2))]

    world_state = build_world_state(objects, containers)

    # 2. 先生成 expected_output（确定所有随机值）
    expected = _build_expected_output(task_type, objects, containers)

    # 3. 从 expected_output 反向构建 utterance 上下文
    ctx = _build_utterance_context(task_type, expected, objects, containers)

    # 4. 过滤兼容模板，选择与 expected_output 一致的模板
    candidates = list(tpl["utterances"])

    # 换线特殊处理：must_match 含 line_id，模板必须含 {line}
    if task_type == "换线":
        candidates = [t for t in candidates if "{line}" in t]

    # 按 expected_output 值过滤语义一致的模板
    candidates = _filter_compatible_templates(task_type, expected, candidates)

    utterance_tpl = random.choice(candidates)
    worker_utterance = fill_template(utterance_tpl, ctx)

    return {
        "id": sample_id,
        "task_type": task_type,
        "worker_utterance": worker_utterance,
        "world_state": world_state,
        "expected_output": expected,
        "eval_criteria": {
            "must_match": tpl["must_match"],
            "optional": [f for f in tpl["fields"] if f not in tpl["must_match"] and f != "action"],
            "match_type": "exact_field_match",
        },
    }


def generate_dataset(
    n_per_task: int = 56,
    output_path: Optional[str] = None,
    id_prefix: str = "train",
    seed: int = 42,
    exclude_utterances: Optional[Set[str]] = None,
) -> List[Dict]:
    """
    生成完整数据集，8 种任务类型各 n_per_task 条。

    内置去重：如果 worker_utterance 已出现过（包括 exclude_utterances），重新生成（最多重试 50 次）。
    若耗尽重试仍重复，则接受（理论上不会发生，模板库已大幅扩充）。

    Args:
        n_per_task: 每种任务类型生成的样本数
        output_path: 保存路径（None 则不写文件）
        id_prefix: ID 前缀（train 或 test）
        seed: 随机种子
        exclude_utterances: 需要排除的话术集合（用于跨数据集去重）
    """
    random.seed(seed)
    samples = []
    seen_utterances: Set[str] = set(exclude_utterances) if exclude_utterances else set()
    # 仅本数据集内避免的重复数
    duplicates_avoided = 0
    # 与 exclude_utterances 冲突的次数
    cross_duplicates_avoided = 0

    MAX_RETRIES = 50
    # 为每条样本预留额外重试熵：每次尝试微调随机状态
    _retry_entropy = seed

    for task_type in VALID_ACTIONS:
        for i in range(n_per_task):
            sid = f"{id_prefix}_{task_type}_{i+1:03d}"
            sample = None
            for _ in range(MAX_RETRIES):
                # 每次重试微调随机状态，增大差异
                _retry_entropy += 7
                random.seed(_retry_entropy)
                candidate = generate_sample(task_type, sid)
                utt = candidate["worker_utterance"]
                if utt not in seen_utterances:
                    sample = candidate
                    seen_utterances.add(utt)
                    break
                # 区分内部重复与跨数据集重复
                if exclude_utterances and utt in exclude_utterances:
                    cross_duplicates_avoided += 1
                else:
                    duplicates_avoided += 1
            else:
                # 耗尽重试仍重复（极少发生），直接接受并告警
                sample = candidate
                print(f"  ⚠️  [{sid}] 重试{MAX_RETRIES}次仍产生重复话术，已接受")

            samples.append(sample)

    if duplicates_avoided > 0 or cross_duplicates_avoided > 0:
        parts = []
        if duplicates_avoided > 0:
            parts.append(f"内部 {duplicates_avoided} 条")
        if cross_duplicates_avoided > 0:
            parts.append(f"跨集 {cross_duplicates_avoided} 条")
        print(f"  🔄 去重：避免 {'，'.join(parts)}重复话术")

    # 最终验证
    all_utterances = [s["worker_utterance"] for s in samples]
    dup_count = len(all_utterances) - len(set(all_utterances))
    if dup_count > 0:
        print(f"  ⚠️  警告：最终数据集仍有 {dup_count} 条重复话术")
    else:
        print(f"  ✅ 话术去重验证通过，{len(samples)} 条全部唯一")

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        print(f"✅ 已生成 {len(samples)} 条样本 → {output_path}")

    return samples


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PRJ-01 灵脑 — 训练/测试数据生成器")
    parser.add_argument("--n-per-task", type=int, default=56, help="每种任务类型的样本数（训练集）")
    parser.add_argument("--train-file", default=TRAIN_FILE, help="训练集输出路径")
    parser.add_argument("--test-file", default=TEST_FILE, help="测试集输出路径")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print("=" * 60)
    print("PRJ-01 灵脑 — 工业指令数据集生成")
    print(f"  训练集每种任务: {args.n_per_task} 条")
    print(f"  测试集每种任务: {max(2, args.n_per_task // 6)} 条")
    print(f"  总任务类型: {len(VALID_ACTIONS)} 种")
    print("=" * 60)

    # 训练集
    train = generate_dataset(
        n_per_task=args.n_per_task,
        output_path=args.train_file,
        id_prefix="train",
        seed=args.seed,
    )
    print(f"  训练集: {len(train)} 条\n")

    # 测试集（不同 seed，ID 不重叠，排除训练集话术避免交叉重复）
    train_utts = set(s["worker_utterance"] for s in train)
    test_n = max(2, args.n_per_task // 6)
    test = generate_dataset(
        n_per_task=test_n,
        output_path=args.test_file,
        id_prefix="test",
        seed=args.seed + 999,
        exclude_utterances=train_utts,
    )
    print(f"  测试集: {len(test)} 条")

    # 打印一条样例
    print("\n─── 样例 ───")
    print(json.dumps(train[0], ensure_ascii=False, indent=2))
