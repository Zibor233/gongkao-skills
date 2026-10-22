---
name: guokao-job-screener
description: Screen 国考招考简章 job tables into recommend, review, and reject tiers with cited remark text. Use for 职位筛选, 岗位匹配, 报考条件核对, or 职位查询. Not for provincial exams.
---

# 国考职位筛选

把一份国考招考简章表格（`.xls` / `.xlsx`）按考生条件筛成三档，输出可人工终审的复核清单。

## 输入

- 内置岗位表：`assets/招考简章-2027.xls`（2027 年度，19,426 个职位）。不传 `--input` 时自动使用。
- 其他年份：用 `--input` 指向新的招考简章，或替换 `assets/` 下的文件；不要改列号。
- 条件文件：复制 `assets/conditions.example.json`，逐项改成考生本人条件。
- 环境：`pip install xlrd openpyxl`。读取 `.xls` 必须有 `xlrd`。

内置表是发布时的快照，报考前应与官方公告核对；年份不符时脚本不会替你判断，需换表。

## 四步工作流

1. **先探表**：内置表已验证。换年份或换文件时，先用 `--lookup` 跑一条已知职位，确认表头行、工作表和 `部门代码/职位代码` 识别正确。表头不在第 1 行是常态，不要手工改列号。
2. **写条件**：按下面字段填写。考生没有的条件写 `false` / `"无"` / `0`，不要留空让脚本猜。
3. **跑筛选**：执行 `screen.py`，得到 `筛选结果.xlsx`、`复核清单.md`、`run_summary.json`。
4. **人工终审**：按 `references/review-checklist.md` 逐条处理「待复核」，以招录单位答复为准。

## 三条硬规则

1. **专业大类不自动判定**。专业列为「XX类」「XX门类」「一级学科」「相关专业」且没有与考生专业名或代码精确匹配时，一律进「待复核」，不得判通过。
2. **风险结论必须附原句**。任何「待复核」事项都要引用「备注」或「专业」列的原文片段，不改写、不概括、不用推断当依据。
3. **不生成不可验证的数据**。不输出上岸概率、竞争比预测、分数线预测；只输出表格中存在的字段和确定性判定。

## 三档判定

- **优先推荐**：硬条件全部通过，且没有复核事项。
- **待复核**：硬条件通过，但存在专业大类歧义、性别表述、证书、体检体能、政治考察、户籍/生源。
- **不推荐**：任一硬条件不满足。

硬条件：学历、学位、专业、政治面貌、基层工作年限、服务基层项目、地区、应届身份、英语四六级、最低服务年限、工作强度。

## 命令

```bash
# 第一次使用：复制条件模板，改成考生本人条件
cp assets/conditions.example.json conditions.json

# 用内置 2027 岗位表筛选
python scripts/screen.py --conditions conditions.json --outdir output

# 换用其他年份的岗位表
python scripts/screen.py --input 招考简章-2028.xls --conditions conditions.json --outdir output

# 单条查询（部门代码/职位代码）；不带 --conditions 时只回显原始字段
python scripts/screen.py --conditions conditions.json --lookup 107105/300110004001

# 只按职位代码查（可能命中多条，逐条列出）
python scripts/screen.py --lookup 300110004001
```

## 条件字段

| 字段 | 取值 | 说明 |
|---|---|---|
| `education` | `大专` / `本科` / `硕士` / `博士` | 考生最高学历 |
| `degree` | `无` / `学士` / `硕士` / `博士` | 与最高学历对应的学位 |
| `major` | 字符串数组 | 写完整专业名，如 `计算机科学与技术`；不要只写「计算机」 |
| `major_codes` | 字符串数组 | 专业代码，如 `080901`；没有就留空数组 |
| `political_status` | `群众` / `共青团员` / `中共党员` / `中共预备党员` | |
| `grassroots_years` | 整数 | 基层工作年限 |
| `service_program` | `无` / `大学生村官` / `三支一扶` / `西部计划` / `特岗教师` / `退役士兵` | 服务基层项目经历 |
| `fresh_graduate` | `true` / `false` | 是否应届 |
| `graduate_year` | 整数，如 `2027` | 毕业年份，用于核对「20XX届」 |
| `regions` | 字符串数组 | 意向地区，省名或市名，如 `湖北`、`武汉` |
| `english` | `{"cet4": true, "cet6": false}` | 四六级是否通过 |
| `accept_service_years` | `true` / `false` | 是否接受「最低服务年限」 |
| `max_service_years` | 整数或 `null` | 可接受的最长服务年限 |
| `accept_intensity` | `true` / `false` | 是否接受经常出差、夜间值班、野外作业等 |
| `gender` | `男` / `女` | 仅用于阅读复核提示，不自动排除 |
| `hukou` | 省名或市名 | 户籍/生源，仅用于阅读复核提示 |

## 输出

- `筛选结果.xlsx`：全量结果，含来源表、行号、三档、判断说明、复核事项、复核依据；表头带筛选，三档配色。
- `复核清单.md`：只列「待复核」，按部门分组，每条附原文依据。
- `run_summary.json`：总数、档位分布、各表条数、表头行、复合主键重复数，便于回归对比。

## 参考

- `references/data-dictionary.md`：27 个字段含义、已知数据坑、2027 简章回归基线。
- `references/remark-rules.md`：备注风险类别、判定口径、已知误判。
- `references/review-checklist.md`：人工终审五步与红线。
