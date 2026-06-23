"""灵脑评测模块单元测试"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from lingnao.eval import safe_parse_json, score_sample, get_nested

# 测试 1: JSON 解析容错
assert safe_parse_json('{"a": 1}') == {"a": 1}, "直接解析失败"
assert safe_parse_json('```json\n{"a": 1}\n```') == {"a": 1}, "代码块解析失败"
assert safe_parse_json('前缀 {"a": 1} 后缀') == {"a": 1}, "嵌套解析失败"
assert safe_parse_json("not json") is None, "非JSON应返回None"
print("✅ safe_parse_json: 4/4")

# 测试 2: 嵌套字段读取
obj = {"a": {"b": {"c": 42}}}
assert get_nested(obj, "a.b.c") == 42
assert get_nested(obj, "a.x") is None
print("✅ get_nested: 2/2")

# 测试 3: 评分逻辑
# 测试: must全对 + optional全对 = 1.0
pred_full = {"action": "取料_放置", "object_filter": {"color": "蓝色"}, "source": "obj_001", "force": "轻"}
exp = {"action": "取料_放置", "object_filter": {"color": "蓝色"}, "source": "obj_001", "force": "轻"}
criteria = {"must_match": ["action", "object_filter.color"], "optional": ["force"]}

s1 = score_sample(pred_full, exp, criteria)
# 公式: (2 + 0.5*1) / (2 + 0.5*1) = 2.5/2.5 = 1.0
assert s1 == 1.0, f"全对+optional对应该1.0, 实际{s1}"

# 测试: must全对 + optional缺失 = 略低于1.0 (技术方案设计: incentivize 全字段输出)
pred_no_opt = {"action": "取料_放置", "object_filter": {"color": "蓝色"}}
s2 = score_sample(pred_no_opt, exp, criteria)
# 公式: (2 + 0.5*0) / (2 + 0.5*1) = 2/2.5 = 0.8
assert 0.7 < s2 < 0.9, f"optional缺失应为0.8左右, 实际{s2}"

# 测试: must错一个
pred_wrong = {"action": "取料_放置", "object_filter": {"color": "红色"}}
s3 = score_sample(pred_wrong, exp, criteria)
# 公式: (1 + 0.5*0) / (2 + 0.5*1) = 1/2.5 = 0.4
assert 0.3 < s3 < 0.5, f"must错一个应为0.4左右, 实际{s3}"

# 测试: None → 0分
s4 = score_sample(None, exp, criteria)
assert s4 == 0.0, f"None应该0分"

print(f"✅ score_sample: full={s1:.2f}, no_opt={s2:.2f}, wrong_color={s3:.2f}, None={s4:.2f}")
print(f"   公式验证: must+optional正确→1.0, optional缺失→0.8, must错→0.4 ✓")

print("\n🏆 评测模块全部验证通过")
