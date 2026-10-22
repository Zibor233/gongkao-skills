# -*- coding: utf-8 -*-
"""加载国考招考简章，定位表头并解析筛选所需字段。

不依赖 pandas：.xls 用 xlrd，.xlsx/.xlsm 用 openpyxl。
"""

import os
import re

CANONICAL_FIELDS = [
    "部门代码", "部门名称", "用人司局", "机构性质", "招考职位", "职位属性",
    "职位分布", "职位简介", "职位代码", "机构层级", "考试类别", "招考人数",
    "专业", "学历", "学位", "政治面貌", "基层工作最低年限",
    "服务基层项目工作经历", "是否在面试阶段组织专业能力测试", "面试人员比例",
    "工作地点", "落户地点", "备注", "部门网站", "咨询电话1", "咨询电话2",
    "咨询电话3",
]

# 只有确认过的同义表头才放进别名，避免把两个不同字段映射到一起。
ALIASES = {
    "部门代码": ("部门代码", "部门编码"),
    "部门名称": ("部门名称", "招录机关"),
    "用人司局": ("用人司局",),
    "机构性质": ("机构性质",),
    "招考职位": ("招考职位", "职位名称"),
    "职位属性": ("职位属性",),
    "职位分布": ("职位分布",),
    "职位简介": ("职位简介",),
    "职位代码": ("职位代码",),
    "机构层级": ("机构层级",),
    "考试类别": ("考试类别",),
    "招考人数": ("招考人数", "招录人数", "计划招录人数"),
    "专业": ("专业", "专业要求"),
    "学历": ("学历", "学历要求"),
    "学位": ("学位", "学位要求"),
    "政治面貌": ("政治面貌",),
    "基层工作最低年限": ("基层工作最低年限", "基层工作年限"),
    "服务基层项目工作经历": ("服务基层项目工作经历", "服务基层项目"),
    "是否在面试阶段组织专业能力测试": ("是否在面试阶段组织专业能力测试",),
    "面试人员比例": ("面试人员比例",),
    "工作地点": ("工作地点",),
    "落户地点": ("落户地点",),
    "备注": ("备注",),
    "部门网站": ("部门网站",),
    "咨询电话1": ("咨询电话1", "咨询电话一"),
    "咨询电话2": ("咨询电话2", "咨询电话二"),
    "咨询电话3": ("咨询电话3", "咨询电话三"),
}

HEADER_LOOKUP = {}
for _canonical, _names in ALIASES.items():
    for _name in _names:
        HEADER_LOOKUP[_name] = _canonical

CN_DIGITS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9}


def cell_text(value):
    """单元格转文本，去掉 Excel 常见的 .0 尾巴与首尾空白。"""
    if value is None:
        return ""
    if isinstance(value, float):
        if value != value:  # NaN
            return ""
        if value.is_integer():
            return str(int(value))
        return ("%s" % value).strip()
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, int):
        return str(value)
    return str(value).replace("\u3000", " ").replace("\xa0", " ").strip()


def code_text(value, width=0):
    """代码转文本：去掉空格、.0，必要时左侧补零。"""
    text = cell_text(value).replace(" ", "")
    text = re.sub(r"\.0+$", "", text)
    if width and re.match(r"^\d+$", text) and len(text) < width:
        text = text.zfill(width)
    return text


def normalize(text):
    text = cell_text(text)
    text = text.replace("\u3000", "").replace("\xa0", "")
    text = re.sub(r"\s+", "", text)
    text = text.replace("（", "(").replace("）", ")")
    return text


def _normalize_header(value):
    return normalize(value).replace(" ", "")


def locate_header(row):
    """在前几行里找表头，返回 {规范字段名: 列号}；找不到返回 None。"""
    normalized = [_normalize_header(v) for v in row]
    mapping = {}
    for index, name in enumerate(normalized):
        canonical = HEADER_LOOKUP.get(name)
        if canonical and canonical not in mapping:
            mapping[canonical] = index
    hits = len(mapping)
    if "部门代码" in mapping and "职位代码" in mapping and hits >= 5:
        return mapping
    if "职位代码" in mapping and "招考职位" in mapping and hits >= 5:
        return mapping
    return None


def _iter_sheets(path):
    extension = os.path.splitext(path)[1].lower()
    if extension == ".xls":
        try:
            import xlrd
        except ImportError:
            raise RuntimeError("读取 .xls 需要 xlrd，请先执行 pip install xlrd")
        book = xlrd.open_workbook(path)
        for name in book.sheet_names():
            sheet = book.sheet_by_name(name)
            rows = (sheet.row_values(i) for i in range(sheet.nrows))
            yield name, rows
        return
    if extension in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError:
            raise RuntimeError("读取 .xlsx 需要 openpyxl，请先执行 pip install openpyxl")
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            for sheet in book.worksheets:
                yield sheet.title, sheet.iter_rows(values_only=True)
        finally:
            book.close()
        return
    raise ValueError("不支持的文件类型：%s（只支持 .xls/.xlsx/.xlsm）" % extension)


def _chain(first, rest):
    for item in first:
        yield item
    for item in rest:
        yield item


def load_jobs(path):
    """读取全部工作表，返回 (jobs, meta)。空表和无表头表会记入 skipped_sheets。"""
    jobs = []
    sheets = []
    skipped = []
    header_rows = {}

    for sheet_name, rows in _iter_sheets(path):
        buffered = []
        header_index = None
        mapping = None
        for index, row in enumerate(rows):
            buffered.append(tuple(row))
            found = locate_header(row) if index < 10 else None
            if found:
                header_index = index
                mapping = found
                break
            if index >= 9:
                break

        if mapping is None:
            skipped.append(sheet_name)
            continue

        header_rows[sheet_name] = header_index + 1
        count = 0
        pending = buffered[header_index + 1:]
        first_data_row = header_index + 2
        last_department = {"code": "", "name": ""}

        for offset, row in enumerate(_chain(pending, rows)):
            job = _row_to_job(row, mapping, sheet_name, first_data_row + offset, last_department)
            if job is None:
                continue
            jobs.append(job)
            count += 1

        sheets.append({
            "name": sheet_name,
            "header_row": header_index + 1,
            "jobs": count,
            "columns_mapped": len(mapping),
        })

    meta = {
        "sheets": sheets,
        "skipped_sheets": skipped,
        "header_rows": header_rows,
    }
    return jobs, meta


def _row_to_job(row, mapping, sheet_name, row_no, last_department):
    def get(field):
        index = mapping.get(field)
        if index is None or index >= len(row):
            return ""
        return row[index]

    department_code = code_text(get("部门代码"), 6)
    job_code = code_text(get("职位代码"), 12)
    position_name = cell_text(get("招考职位"))

    if not department_code and job_code and last_department["code"]:
        department_code = last_department["code"]
    elif department_code:
        last_department["code"] = department_code

    department_name = cell_text(get("部门名称"))
    if not department_name and job_code and last_department["name"]:
        department_name = last_department["name"]
    elif department_name:
        last_department["name"] = department_name

    if not position_name and not job_code:
        return None
    if position_name.replace(" ", "") in ("合计", "总计", "小计"):
        return None

    job = {
        "source_sheet": sheet_name,
        "row_no": row_no,
        "dept_code": department_code,
        "dept_name": department_name,
        "bureau": cell_text(get("用人司局")),
        "org_nature": cell_text(get("机构性质")),
        "position_name": position_name,
        "position_attr": cell_text(get("职位属性")),
        "position_dist": cell_text(get("职位分布")),
        "position_desc": cell_text(get("职位简介")),
        "job_code": job_code,
        "level": cell_text(get("机构层级")),
        "exam_type": cell_text(get("考试类别")),
        "headcount": _headcount(get("招考人数")),
        "major_text": cell_text(get("专业")),
        "education_text": cell_text(get("学历")),
        "degree_text": cell_text(get("学位")),
        "political_text": cell_text(get("政治面貌")),
        "grassroots_text": cell_text(get("基层工作最低年限")),
        "service_text": cell_text(get("服务基层项目工作经历")),
        "special_test": cell_text(get("是否在面试阶段组织专业能力测试")),
        "interview_ratio": cell_text(get("面试人员比例")),
        "work_location": cell_text(get("工作地点")),
        "settle_location": cell_text(get("落户地点")),
        "remark": cell_text(get("备注")),
        "dept_site": cell_text(get("部门网站")),
        "phone1": cell_text(get("咨询电话1")),
        "phone2": cell_text(get("咨询电话2")),
        "phone3": cell_text(get("咨询电话3")),
    }
    job["job_key"] = "%s/%s" % (job["dept_code"] or "?", job["job_code"] or "?")

    education = parse_education(job["education_text"])
    degree = parse_degree(job["degree_text"])
    job["education_levels"] = education["levels"]
    job["degree_levels"] = degree["levels"]
    job["degree_matching"] = degree["matching"]
    job["major_codes"] = extract_major_codes(job["major_text"])
    return job


def _headcount(value):
    text = cell_text(value)
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else 0


def _edu_level(text):
    if "博士" in text:
        return 4
    if "硕士" in text or "研究生" in text:
        return 3
    if "本科" in text:
        return 2
    if "大专" in text or "专科" in text or "高职" in text:
        return 1
    return 0


def parse_education(text):
    """返回 {"raw": 原文, "levels": 允许的学历层级或 None(不限), "ok": 是否可解析}。

    层级：1 大专，2 本科，3 硕士，4 博士。
    """
    raw = cell_text(text)
    compact = normalize(raw)
    if not compact or compact in ("不限", "无限制", "不限学历"):
        return {"raw": raw, "levels": None, "ok": True}

    base = _edu_level(compact)
    if not base:
        return {"raw": raw, "levels": [], "ok": False}

    levels = set()
    if "及以上" in compact or "以上" in compact:
        levels.update(range(base, 5))
    else:
        levels.add(base)

    for segment in re.split(r"[或、,，/]", compact):
        level = _edu_level(segment)
        if level:
            levels.add(level)

    # 只写「研究生」时，博士通常也符合；写「硕士研究生」则只按硕士处理。
    if compact in ("研究生", "研究生学历") or compact.startswith("研究生("):
        if "硕士" not in compact:
            levels.add(4)

    return {"raw": raw, "levels": sorted(levels), "ok": True}


def _degree_level(text):
    if "博士" in text:
        return 3
    if "硕士" in text:
        return 2
    if "学士" in text:
        return 1
    return 0


def parse_degree(text):
    """返回 {"raw", "levels", "matching"}。matching 表示「与最高学历相对应」。"""
    raw = cell_text(text)
    compact = normalize(raw)
    if not compact or compact in ("不限", "无限制", "不限学位"):
        return {"raw": raw, "levels": None, "matching": False}
    if "相对应" in compact or "相应学位" in compact:
        return {"raw": raw, "levels": None, "matching": True}

    base = _degree_level(compact)
    if not base:
        return {"raw": raw, "levels": [], "matching": False}

    if "及以上" in compact or "以上" in compact:
        levels = list(range(base, 4))
    else:
        levels = {base}
        for segment in re.split(r"[或、,，/]", compact):
            level = _degree_level(segment)
            if level:
                levels.add(level)
        levels = sorted(levels)
    return {"raw": raw, "levels": levels, "matching": False}


def extract_major_codes(text):
    """抽取专业代码。只认 4 位学科代码和 6 位专业代码，排除 19xx/20xx 年份。"""
    codes = set()
    for match in re.finditer(r"(?<!\d)(\d{4}|\d{6})(?!\d)", cell_text(text)):
        code = match.group(1)
        if len(code) == 4 and 1900 <= int(code) <= 2100:
            continue
        codes.add(code)
    return sorted(codes)


MAJOR_SEGMENT_PATTERN = re.compile(r"(博士研究生|硕士研究生|本科|研究生)\s*[:：]")


def select_major_segment(text, user_level):
    """按学历选择专业段。返回 (文本, 是否分段, 是否命中考生学历段)。"""
    raw = cell_text(text)
    matches = list(MAJOR_SEGMENT_PATTERN.finditer(raw))
    if not matches:
        return raw, False, True

    segments = {}
    for index, match in enumerate(matches):
        label = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        if label == "博士研究生":
            level = 4
        elif label in ("硕士研究生", "研究生"):
            level = 3
        else:
            level = 2
        segments.setdefault(level, "")
        segments[level] += raw[start:end].strip()

    if user_level in segments and segments[user_level]:
        return segments[user_level], True, True
    return raw, True, False


def parse_chinese_number(text):
    """解析「两」「五」「十一」「二十」这类数字；解析不了返回 None。"""
    if not text:
        return None
    if re.match(r"^\d+$", text):
        return int(text)
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = CN_DIGITS.get(left, 1) if left else 1
        ones = CN_DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    return CN_DIGITS.get(text)


def parse_years(text):
    """从文本中取第一个年限；「无限制/不限」返回 0，找不到返回 None。"""
    compact = normalize(text)
    if not compact:
        return None
    if "无限制" in compact or "不限" in compact or "无" == compact:
        return 0
    match = re.search(r"(\d+|[一二三四五六七八九十两]+)\s*年", compact)
    if not match:
        return None
    return parse_chinese_number(match.group(1))


def split_sentences(text):
    """按中文句号/分号/换行切句，用于引用备注原句。"""
    raw = cell_text(text)
    parts = re.split(r"[。；;\n\r]+", raw)
    return [part.strip() for part in parts if part.strip()]
