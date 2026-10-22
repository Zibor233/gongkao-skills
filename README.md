# 公考双 Skill

给 AI Agent（TRAE 等支持 `SKILL.md` 的工具）用的两个公考 Skill：

| Skill | 干什么 | 内置数据 |
|---|---|---|
| [guokao-job-screener](skills/guokao-job-screener/) | 按考生条件筛国考招考简章，输出「优先推荐 / 待复核 / 不推荐」三档 + 复核清单 | 2027 年度招考简章，19,426 个职位 |
| [xingce-question-bank](skills/xingce-question-bank/) | 在本地行测 Markdown 题库上按模块/年份/题型检索组卷，练习卷与答案页分离 | 无（题库需自行下载） |

设计上只做「翻表、拆题、按规则筛、把原文留下」这类可验证的活，不替考生下判断：不输出上岸概率、竞争比、分数线预测。

## 目录结构

```text
gongkao-skills/
├── skills/
│   ├── guokao-job-screener/
│   │   ├── SKILL.md                        # Agent 读取的入口说明
│   │   ├── assets/
│   │   │   ├── 招考简章-2027.xls            # 内置岗位表（2027 年度）
│   │   │   └── conditions.example.json     # 考生条件模板
│   │   ├── references/                     # 字段字典、备注规则、终审清单
│   │   └── scripts/
│   │       ├── screen.py                   # 筛选主脚本
│   │       └── jobs.py                     # 读表与字段解析
│   └── xingce-question-bank/
│       ├── SKILL.md
│       ├── references/corpus-format.md     # 题库格式说明
│       └── scripts/
│           ├── practice.py                 # 组卷主脚本
│           └── bank.py                     # Markdown 题库解析
├── LICENSE
└── README.md
```

## 前置要求

- Python 3.8+
- 选岗 Skill 需要表格依赖：`pip install xlrd openpyxl`（读 `.xls` 必须有 `xlrd`）
- 组卷 Skill 只用标准库，无需安装依赖
- 一个会读 `SKILL.md` 的 Agent（TRAE 等）

## 安装

Skill 的安装位置是 `.trae/skills/`，可以把整个仓库或单个 Skill 目录放进去。

### 方式一：clone 后复制（推荐）

```bash
git clone https://github.com/zibor233/gongkao-skills.git
```

把需要的 Skill 目录复制到工程的 `.trae/skills/` 下：

```text
你的工程/
└── .trae/
    └── skills/
        ├── guokao-job-screener/
        └── xingce-question-bank/
```

Windows 下用资源管理器直接拖进去也一样。装好后重启会话，Agent 会自动识别 `SKILL.md`。

### 方式二：只装一个

只要选岗：

```bash
git clone --depth 1 https://github.com/zibor233/gongkao-skills.git
# 只复制 skills/guokao-job-screener/ 到 .trae/skills/
```

### 方式三：让 Agent 自己装

把仓库地址丢给 Agent，说：

```text
把这个仓库里的 guokao-job-screener 和 xingce-question-bank
复制到当前工程的 .trae/skills/ 目录下
```

## 教程一：国考选岗

### 1. 用内置岗位表跑一次

`assets/招考简章-2027.xls` 已随 Skill 分发，不传 `--input` 时自动使用。

```bash
cd .trae/skills/guokao-job-screener

# 复制条件模板，改成你自己的条件
cp assets/conditions.example.json conditions.json

# 跑筛选（Windows PowerShell 用 copy 代替 cp）
python scripts/screen.py --conditions conditions.json --outdir output
```

条件文件字段说明：

| 字段 | 取值 | 说明 |
|---|---|---|
| `education` | `大专`/`本科`/`硕士`/`博士` | 最高学历 |
| `degree` | `无`/`学士`/`硕士`/`博士` | 与最高学历对应的学位 |
| `major` | 字符串数组 | 写完整专业名，如 `计算机科学与技术`，不要只写「计算机」 |
| `major_codes` | 字符串数组 | 专业代码，如 `080901`；没有就留空数组 |
| `political_status` | `群众`/`共青团员`/`中共党员`/`中共预备党员` | |
| `grassroots_years` | 整数 | 基层工作年限 |
| `service_program` | `无`/`大学生村官`/`三支一扶`/`西部计划`/`特岗教师`/`退役士兵` | 服务基层项目经历 |
| `fresh_graduate` | `true`/`false` | 是否应届 |
| `graduate_year` | 整数，如 `2027` | 毕业年份，用于核对「20XX届」 |
| `regions` | 字符串数组 | 意向地区，省名或市名，如 `湖北`、`武汉`；不限填 `[]` |
| `english` | `{"cet4": true, "cet6": false}` | 四六级是否通过 |
| `accept_service_years` | `true`/`false` | 是否接受「最低服务年限」 |
| `max_service_years` | 整数或 `null` | 可接受的最长服务年限 |
| `accept_intensity` | `true`/`false` | 是否接受经常出差、夜间值班、野外作业等 |
| `gender` | `男`/`女` | 仅用于生成复核提示，不自动排除 |
| `hukou` | 省名或市名 | 户籍/生源，仅用于生成复核提示 |

考生没有的条件写 `false` / `"无"` / `0`，不要留空让脚本猜。

### 2. 看结果

跑完在 `output/`（或 `--outdir` 指定目录）下得到三个文件：

- `筛选结果.xlsx`：全量结果，含来源表、行号、三档、判断说明、复核事项、复核依据，表头带筛选、三档配色。
- `复核清单.md`：只列「待复核」，按部门分组，每条附原文依据。
- `run_summary.json`：总数、档位分布、各表条数、表头行、复合主键重复数，便于回归对比。

终端同时会打印档位分布和各工作表条数：

```text
总职位数 19426
优先推荐 4
待复核 969
不推荐 18453
工作表：中央党群机关 99 条（表头第 2 行）；……
```

「待复核」条数通常远大于「优先推荐」，这是正常现象：专业大类、性别表述、证书、体检体能、政治考察、户籍/生源这些无法从表格确定的项，一律进待复核，不替你下结论。

`--max-review 3` 可以限制复核清单输出条数，先看几条再决定要不要全量导出。

### 3. 单条查询

报名前想确认某个职位：

```bash
# 部门代码/职位代码
python scripts/screen.py --conditions conditions.json --lookup 107105/300110004001

# 只按职位代码（可能命中多条，逐条列出）
python scripts/screen.py --lookup 300110004001
```

不带 `--conditions` 时只回显原始字段，不做判定。

### 4. 换年份的岗位表

```bash
python scripts/screen.py --input 招考简章-2028.xls --conditions conditions.json --outdir output
```

或直接替换 `assets/` 下的文件。**不要改列号**——脚本会自己找表头行（表头不在第 1 行是常态）。换表后先用 `--lookup` 跑一条已知职位，确认表头行、工作表和 `部门代码/职位代码` 识别正确，再跑全量。

内置表是发布时的快照，报考前务必与官方公告核对。

### 5. 三条硬规则

1. **专业大类不自动判定**。专业列为「XX类」「XX门类」「一级学科」「相关专业」且没有与考生专业名或代码精确匹配时，一律进「待复核」。
2. **风险结论必须附原句**。任何「待复核」事项都引用「备注」或「专业」列的原文片段，不改写、不概括。
3. **不生成不可验证的数据**。不输出上岸概率、竞争比预测、分数线预测。

`references/review-checklist.md` 是人工终审的五步流程与红线，最终以招录单位答复为准。

## 教程二：行测组卷

### 1. 先准备题库

题库不在本仓库内，需从原仓库自行下载：[ERRRC/xingcezhenti](https://github.com/ERRRC/xingcezhenti)。

```bash
git clone https://github.com/ERRRC/xingcezhenti.git
# 得到 xingcezhenti-main/ 目录，含 01-政治理论 到 06-资料分析 六个模块
```

题库目录未标注许可证，请只在本机使用，不要再分发。

### 2. 看规模

```bash
cd .trae/skills/xingce-question-bank
python scripts/practice.py --root /path/to/xingcezhenti-main --stats
```

输出示例：

```text
题库文件：2962
不同试卷：515
题目总数：58890
不同 qid：27473
重复出现：31417
扫描耗时：5.5s
```

注意「题目总数」远大于「不同 qid」：同一道题会在不同省份卷中重复出现，组卷默认按 qid 去重。需要原卷全量时再加 `--allow-duplicates`。

`--root` 省略时会在当前目录及上级查找 `xingcezhenti-main`。

### 3. 组卷

```bash
# 2024 年图形推理 10 题，固定 seed 保证可复现
python scripts/practice.py --root /path/to/xingcezhenti-main \
  --module 判断推理 --type 图形推理 --year 2024 \
  --count 10 --seed 42 --outdir ./practice-output

# 资料分析，自动带材料
python scripts/practice.py --root /path/to/xingcezhenti-main \
  --module 资料分析 --year 2024 --count 5 --seed 42

# 按 qid 取题
python scripts/practice.py --root /path/to/xingcezhenti-main --qid 1796080,1796082

# 关键词检索题干、选项、解析、试卷名
python scripts/practice.py --root /path/to/xingcezhenti-main --keyword 雄安 --count 5
```

输出示例：

```text
筛选后题目：150
已生成：10 题
练习卷：practice-output/练习卷.md
答案页：practice-output/练习卷-答案.md
```

`练习卷.md` 只放题干、选项和资料分析材料，**不含答案**；`练习卷-答案.md` 放答案、来源试卷和官方解析。用 `--name 图形推理` 可自定义文件名前缀。

### 4. 参数速查

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

## 用 Agent 跑

装好 Skill 后直接说需求即可，Agent 会读 `SKILL.md` 走上面的流程：

```text
帮我筛一下国考岗位，本科计算机科学与技术，2027 届，党员，四六级都没过
```

```text
给我来一套 2024 年图形推理 10 题，答案单独放
```

## 常见问题

**Q：为什么「待复核」有上万条？**
A：这是设计意图。表格里说不清的部分（专业大类、证书、体检体能、户籍）不替你判断，全部捞出来交给人。真正常用的做法是拿 `复核清单.md` 挨个打电话确认。

**Q：`ImportError: No module named xlrd`？**
A：读 `.xls` 必须装 `xlrd`：`pip install xlrd openpyxl`。

**Q：岗位表报错找不对表头/列错位？**
A：先确认用的是脚本支持的简章格式。表头不在第 1 行是常态，脚本会自动定位；换年份换文件后先用 `--lookup` 验证一条已知职位。

**Q：组卷抽到的题题干是空的或带图？**
A：部分题目题干依赖图片，Markdown 里保留了原图引用。`--stats` 会打印「含图题目」数量。

**Q：练习卷里出现答案了？**
A：不会。答案隔离在 `-答案.md` 里，这是脚本的硬规则。

**Q：为什么任务说「没有符合条件的题目」？**
A：筛选条件太窄，放宽 `--module` / `--year` / `--type`，或去掉 `--count` 限制先看池子大小。

## 数据与许可证

- 代码与文档以 [MIT](LICENSE) 授权。
- `skills/guokao-job-screener/assets/招考简章-2027.xls` 是官方公开发布的招考简章，随 Skill 分发只为方便使用；数据以官方公告为准，MIT 授权不覆盖该文件的内容。
- 行测题库（ERRRC/xingcezhenti）**不在本仓库内**，其许可证状态未知，请勿打包或再分发。

两个 Skill 都只做确定性检索和整理，不构成报考建议，不对报考结果负责。
