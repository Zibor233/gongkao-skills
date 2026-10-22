---
name: xingce-question-bank
description: Index local xingcezhenti Markdown question banks and generate practice sets with separate answer pages. Use for 行测刷题, 真题检索, 组卷, 模块/年份/题型筛选. Not for job screening or non-行测 exams.
---

# 行测题库组卷

在本地 `xingcezhenti` 题库上按模块、年份、地区、题型检索并组卷，输出「练习卷 + 答案页」。题库不随 Skill 分发。

## 输入

- 题库目录：`xingcezhenti-main`，含 `01-政治理论` 到 `06-资料分析` 六个模块。来源是 [ERRRC/xingcezhenti](https://github.com/ERRRC/xingcezhenti)，仓库未标注许可证，**不要打包或再分发题库**。
- 环境：Python 3.8+，只用标准库，无需安装依赖。
- 默认在当前目录及上级查找 `xingcezhenti-main`；不在这些位置时用 `--root` 指定。

## 工作流

1. **先看规模**：跑 `--stats`，确认文件数、试卷数、题目数和各模块分布。
2. **筛题组卷**：用模块/年份/地区/题型筛题，固定 `--seed` 保证可复现。
3. **分离答案**：练习卷只放题干和选项，答案与解析写进 `-答案.md`；用 qid 回查原卷。

## 命令

```bash
# 题库统计
python scripts/practice.py --root ../xingcezhenti-main --stats

# 2024 年图形推理 10 题
python scripts/practice.py --root ../xingcezhenti-main \
  --module 判断推理 --type 图形推理 --year 2024 \
  --count 10 --seed 42 --outdir ./practice-output

# 资料分析，自动带材料
python scripts/practice.py --root ../xingcezhenti-main \
  --module 资料分析 --year 2024 --count 5 --seed 42

# 按 qid 取题
python scripts/practice.py --root ../xingcezhenti-main --qid 1796080,1796082

# 关键词检索题干、选项、解析、试卷名
python scripts/practice.py --root ../xingcezhenti-main --keyword 雄安 --count 5
```

## 参数

| 参数 | 说明 |
|---|---|
| `--root` | 题库目录；省略时自动查找 |
| `--module` | 模块，如 `判断推理`、`05`、`资料分析` |
| `--year` | 年份，如 `2024`、`2024,2025`、`2020-2024` |
| `--region` | 地区，如 `四川` |
| `--type` | 题型，如 `图形推理`、`逻辑填空` |
| `--qid` | 按 qid 取题，逗号分隔 |
| `--keyword` | 关键词，匹配题干、选项、解析、试卷名 |
| `--count` | 题量，默认 20；`0` 表示全部 |
| `--seed` | 随机种子，默认 2027 |
| `--outdir` | 输出目录，默认 `practice-output` |
| `--name` | 输出文件名前缀，默认 `练习卷` |
| `--allow-duplicates` | 保留同一 qid 在不同省份卷中的重复题 |
| `--stats` | 只打印统计，不组卷 |

## 输出

- `练习卷.md`：题干、选项、资料分析材料；**不含答案和解析**。
- `练习卷-答案.md`：答案、来源试卷、官方解析。
- 默认按 qid 去重，保留最早出现的一条；题库共 58,890 条题目记录、27,473 个不同 qid。

## 规则

1. **答案隔离**：练习卷不得出现 `**答案**` 或 `**官方解析**`；答案只放在答案页。
2. **先查重**：同一道题会在不同省份卷中重复出现，默认按 qid 去重；需要原卷全量时再加 `--allow-duplicates`。
3. **保留溯源**：每题保留 qid 和来源试卷；不要改写题干、选项和答案。
4. **不分发题库**：仓库未标注许可证，题库只在本机使用；分享 Skill 时不附带题库。
5. **不承诺效果**：只做检索和组卷，不输出提分承诺、押题或命中率。

## 参考

- `references/corpus-format.md`：题库目录、字段、题目块、材料结构和已知边界。
