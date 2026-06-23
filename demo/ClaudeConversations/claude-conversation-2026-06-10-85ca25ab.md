# Claude Conversation Log

Session ID: 85ca25ab-b923-4684-8991-030d95a3abd7
Date: 2026-06-10 08:46:37

---

## 👤 User

将生成数据集的部分工人的话术再增加一些，包括训练集和测试集，测试集要有100条，训练集要有400-500条

---

## 🤖 Claude

Now I understand the full picture. Let me analyze the current state and plan the changes:

**Current state:**
- Training: `n_per_task=12` × 8 tasks = **96 samples**
- Test: `n_per_task=2` × 8 tasks = **16 samples**
- Templates per task: 14-30 utterances

**Target:**
- Training: 400-500 samples → need ~56 per task (56×8=**448**)
- Test: 100 samples → need ~13 per task (13×8=**104**)

I need to:
1. Add more worker utterance templates to each task type
2. Update generation parameters in `run_demo.py`

Let me start by adding more utterances to each task type, then update the generation logic.

---

## 🤖 Claude

Now I need to update `run_demo.py` to generate larger datasets. Let me update all the `n_per_task` parameters.

---

## 🤖 Claude

Now update the `data_generator.py` CLI defaults and `generate_dataset` function signature:

---

## 🤖 Claude

I need to check my 状态查询 additions — the new "运行状态" templates don't match the schema's valid query types. Let me fix that.

---

## 🤖 Claude

Now let me test the data generation to verify everything works:

---

## 🤖 Claude

There's a syntax error. Let me check the file around the issue:

---

## 🤖 Claude

I see the issue — line 184 is missing the `],` that closes the `utterances` list. Let me fix it:

---

## 🤖 Claude

Basic test passes. Now let me run a full-scale generation test:

---

## 🤖 Claude

The 协作等待 (collaborative waiting) task has too few variable-rich templates, causing major duplication. Let me add more diverse templates:

---

## 🤖 Claude

I also need to update the `TEMPLATE_COMPAT` mappings so the new templates aren't filtered out:

---

## 🤖 Claude

Now let me re-run the full-scale generation test:

---

## 🤖 Claude

All 448 training samples and 104 test samples are unique with zero cross-duplicates. Let me do a final end-to-end verification:

---

## 🤖 Claude

The utterances look good and diverse. Let me verify the existing data files aren't stale and run one final end-to-end check:

---

## 🤖 Claude

All changes are complete and verified. Here's a summary of what was done:

## 变更总结

### 话术模板扩充（`lingnao/data_generator.py`）

每个任务类型的工人话术模板大幅增加：

| 任务类型 | 原有 | 现在 | 新增 |
|---------|------|------|------|
| 取料_放置 | 18 | **32** | +14 |
| 装配 | 16 | **30** | +14 |
| 换线 | 15 | **25** | +10 |
| 质检 | 15 | **25** | +10 |
| 搬运 | 14 | **25** | +11 |
| 异常应对 | 30 | **35** | +5 |
| 状态查询 | 24 | **31** | +7 |
| 协作等待 | 24 | **52** | +28 |
| **总计** | **156** | **255** | **+99** |

### 数据集规模调整（`run_demo.py`）

- **训练集**: `n_per_task` 从 12 → **56**，总计 56×8 = **448 条**（在 400-500 范围内）
- **测试集**: `n_per_task` 从 2 → **13**，总计 13×8 = **104 条**（接近目标 100 条）

### 验证结果

- ✅ 训练集 448 条，**全部唯一**，零内部重复
- ✅ 测试集 104 条，**全部唯一**
- ✅ 训练集与测试集之间 **零交叉重复**
- ✅ 8 种任务类型分布均匀

运行 `python run_demo.py --gen-data` 即可重新生成新规模的数据集。

---

