# -*- coding: utf-8 -*-
"""解析 xingcezhenti 的行测 Markdown 题库。

题库结构：每个模块一个目录，每套卷的每个模块一篇 Markdown。
题干、选项、答案、官方解析、qid 都在正文中；资料分析为「材料 -> 小题」结构。
"""

import hashlib
import os
import re
from collections import Counter

EXCLUDED_DIRS = {"90-图片"}
EXP_MARKER = "**官方解析**"

HEAD_RE = re.compile(
    r"^(#{2,3})[ \t\u3000]*第[ \t\u3000]*(\d+)[ \t\u3000]*题"
    r"[ \t\u3000]*(?:<sub>[ \t\u3000]*qid[ \t]*(\d+)[ \t]*·[ \t]*([^<]+?)[ \t]*</sub>)?[ \t]*$",
    re.M,
)
MATERIAL_RE = re.compile(r"^##[ \t\u3000]+材料[ \t\u3000]*(\d+)[ \t]*$", re.M)
OPTION_RE = re.compile(r"^-[ \t\u3000]*\*\*([A-E])\*\*[.．][ \t\u3000]*(.*)$", re.M)
ANSWER_RE = re.compile(r"\*\*答案\*\*[：:][ \t\u3000]*(.+?)[ \t]*$", re.M)
PLACEHOLDER_RE = re.compile(r"(?m)^-[ \t\u3000]*（选项）\[\][ \t]*$")


def parse_frontmatter(text):
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not match:
        return {}
    meta = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta


def line_number(text, position):
    return text.count("\n", 0, position) + 1


def plain_text(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_block(block, heading, meta):
    """解析单个题目块，返回题目字典。"""
    lines = block.splitlines()
    body = "\n".join(lines[1:]).strip()
    body = re.sub(r"\n---[ \t]*$", "", body).strip()

    answer_match = ANSWER_RE.search(body)
    answer = answer_match.group(1).strip() if answer_match else ""

    explanation = ""
    explanation_index = body.find(EXP_MARKER)
    if explanation_index >= 0:
        main = body[:explanation_index].strip()
        explanation = body[explanation_index + len(EXP_MARKER):].strip()
    else:
        main = body

    main = ANSWER_RE.sub("", main).strip()
    option_matches = list(OPTION_RE.finditer(main))
    options = []
    if option_matches:
        stem = main[:option_matches[0].start()].strip()
        for option in option_matches:
            text = option.group(2).strip()
            correct = "✅" in text
            text = text.replace("✅", "").strip()
            options.append({
                "label": option.group(1),
                "text": text,
                "correct": correct,
            })
    else:
        stem = main
    stem = PLACEHOLDER_RE.sub("", stem).strip()
    explanation = re.sub(r"\n---[ \t]*$", "", explanation).strip()

    qid = heading.group(3) or ""
    qtype = (heading.group(4) or "").strip()
    has_image = "<img" in block or "![" in block

    return {
        "qid": qid,
        "type": qtype,
        "answer": answer,
        "stem": stem,
        "options": options,
        "explanation": explanation,
        "stem_preview": plain_text(stem)[:90],
        "option_count": len(options),
        "has_image": has_image,
        "paper": meta.get("试卷", ""),
        "year": meta.get("年份", ""),
        "region": meta.get("地区", ""),
    }


def parse_file(path, root, module, light=False):
    """解析一篇 Markdown，返回该篇的题目列表。light=True 时不带题干全文。"""
    with open(path, "r", encoding="utf-8-sig") as handle:
        text = handle.read()
    meta = parse_frontmatter(text)
    if module:
        meta["模块"] = module
    relative = os.path.relpath(path, root).replace("\\", "/")
    headings = list(HEAD_RE.finditer(text))
    materials = list(MATERIAL_RE.finditer(text))
    questions = []

    for index, heading in enumerate(headings):
        end_position = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[heading.start():end_position]

        material = None
        for candidate in materials:
            if candidate.start() < heading.start():
                material = candidate
            else:
                break

        material_title = ""
        material_text = ""
        material_key = ""
        material_start_line = None
        material_end_line = None
        if material:
            next_heading = next((h for h in headings if h.start() > material.start()), None)
            material_end_position = next_heading.start() if next_heading else len(text)
            material_title = "材料 %s" % material.group(1)
            material_text = text[material.start():material_end_position].strip()
            material_text = re.sub(r"\n---[ \t]*$", "", material_text).strip()
            material_key = hashlib.md5(
                re.sub(r"\s+", "", material_text).encode("utf-8")).hexdigest()
            material_start_line = line_number(text, material.start())
            material_end_line = line_number(text, material_end_position)

        question = parse_block(block, heading, meta)
        question.update({
            "module": meta.get("模块", module or ""),
            "file": relative,
            "start_line": line_number(text, heading.start()),
            "end_line": line_number(text, end_position),
            "material_title": material_title,
            "material_key": material_key,
            "material_start_line": material_start_line,
            "material_end_line": material_end_line,
        })
        if not light:
            question["material_text"] = material_text
        questions.append(question)

    return questions


def iter_files(root):
    for name in sorted(os.listdir(root)):
        directory = os.path.join(root, name)
        if not os.path.isdir(directory):
            continue
        if name in EXCLUDED_DIRS or not re.match(r"^\d{2}-", name):
            continue
        for filename in sorted(os.listdir(directory)):
            if filename.endswith(".md") and not filename.startswith("."):
                yield name, os.path.join(directory, filename)


def scan_bank(root):
    """扫描全库，返回 (light 题目列表, 文件数, 模块计数)。"""
    items = []
    files = 0
    module_counter = Counter()
    for module, path in iter_files(root):
        files += 1
        questions = parse_file(path, root, module, light=True)
        items.extend(questions)
        module_counter[module] += len(questions)
    return items, files, module_counter


def load_questions(items, root):
    """按文件分组加载选中题目的全文，避免重复读同一篇。"""
    grouped = {}
    for item in items:
        grouped.setdefault(item["file"], []).append(item)

    loaded = {}
    for relative, group in grouped.items():
        path = os.path.join(root, relative)
        questions = parse_file(path, root, group[0]["module"], light=False)
        by_qid = {}
        for question in questions:
            by_qid.setdefault(question["qid"], question)
        for item in group:
            question = by_qid.get(item["qid"])
            if question:
                loaded[(item["file"], item["qid"])] = question
    return loaded
