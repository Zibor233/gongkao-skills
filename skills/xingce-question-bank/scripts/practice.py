# -*- coding: utf-8 -*-
"""从 xingcezhenti 本地题库组卷，输出练习卷与答案页。"""

import argparse
import os
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime

from bank import load_questions, parse_file, scan_bank


def split_values(text):
    return [value.strip() for value in (text or "").split(",") if value.strip()]


def is_bank(root):
    try:
        names = os.listdir(root)
    except OSError:
        return False
    return any(os.path.isdir(os.path.join(root, name)) and re.match(r"^\d{2}-", name)
               for name in names)


def resolve_root(value):
    if value:
        root = os.path.abspath(value)
    else:
        root = None
        for base in (os.getcwd(), os.path.dirname(os.getcwd())):
            candidate = os.path.join(base, "xingcezhenti-main")
            if is_bank(candidate):
                root = candidate
                break
        if not root:
            raise SystemExit("未找到 xingcezhenti-main，请用 --root 指向题库目录")
    if not is_bank(root):
        raise SystemExit("题库目录不正确：%s" % root)
    return root


def match_module(module, spec):
    if not spec:
        return True
    for part in split_values(spec):
        if module == part or module.startswith(part) or part in module:
            return True
    return False


def match_year(year, spec):
    if not spec:
        return True
    for part in split_values(spec):
        if "-" in part:
            low, high = part.split("-", 1)
            if low <= year <= high:
                return True
        elif year == part:
            return True
    return False


def match_text(value, spec):
    if not spec:
        return True
    return any(part in value for part in split_values(spec))


def filter_items(items, args):
    qids = set(split_values(args.qid))
    result = []
    for item in items:
        if not match_module(item["module"], args.module):
            continue
        if not match_year(item["year"], args.year):
            continue
        if not match_text(item["region"], args.region):
            continue
        if not match_text(item["type"], args.type):
            continue
        if qids and item["qid"] not in qids:
            continue
        result.append(item)
    return result


def filter_keyword(items, root, keyword):
    """关键词命中题干、选项、解析或试卷名；按文件分组，避免重复解析。"""
    needle = keyword.lower()
    grouped = {}
    for item in items:
        grouped.setdefault(item["file"], []).append(item)

    kept = []
    for relative, group in grouped.items():
        path = os.path.join(root, relative)
        questions = parse_file(path, root, group[0]["module"], light=False)
        by_qid = {}
        for question in questions:
            by_qid.setdefault(question["qid"], question)
        for item in group:
            question = by_qid.get(item["qid"])
            if not question:
                continue
            haystack = " ".join([
                question["paper"],
                question["type"],
                question["stem"],
                " ".join(option["text"] for option in question["options"]),
                question["explanation"],
            ])
            if needle in haystack.lower():
                kept.append(item)
    return kept


def dedupe_by_qid(items):
    """同一道题会在不同省份卷里重复出现，按 qid 去重，保留最早的一条。"""
    ordered = sorted(items, key=lambda item: (item["year"], item["file"], item["start_line"]))
    seen = set()
    result = []
    for item in ordered:
        if item["qid"] in seen:
            continue
        seen.add(item["qid"])
        result.append(item)
    return result


def select_items(pool, args):
    if args.qid:
        order = {qid: index for index, qid in enumerate(split_values(args.qid))}
        pool = [item for item in pool if item["qid"] in order]
        pool.sort(key=lambda item: order[item["qid"]])
        return pool

    if args.count <= 0 or args.count >= len(pool):
        selected = list(pool)
    else:
        selected = random.Random(args.seed).sample(pool, args.count)
    selected.sort(key=lambda item: (
        item.get("material_key") or "~" + item["file"],
        item["file"],
        item["start_line"],
    ))
    return selected


def rewrite_assets(text, source_file, outdir):
    """把题目里的相对图片路径改成相对输出目录的路径。"""
    if not text:
        return text
    base = os.path.dirname(source_file)

    def replace(path):
        if not path or path.startswith(("http://", "https://", "data:", "file:")):
            return path
        if os.path.isabs(path):
            return path
        absolute = os.path.normpath(os.path.join(base, path))
        if not os.path.exists(absolute):
            return path
        try:
            relative = os.path.relpath(absolute, outdir)
        except ValueError:
            # Windows 跨盘符无法计算相对路径，退回绝对路径。
            relative = absolute
        return relative.replace("\\", "/")

    text = re.sub(r'(src=["\'])([^"\']+)(["\'])',
                  lambda match: match.group(1) + replace(match.group(2)) + match.group(3), text)
    text = re.sub(r'(!\[[^\]]*\]\()([^)]+)(\))',
                  lambda match: match.group(1) + replace(match.group(2)) + match.group(3), text)
    return text


def prepare_question(question, root, outdir):
    source_file = os.path.join(root, question["file"])
    prepared = dict(question)
    prepared["stem"] = rewrite_assets(prepared["stem"], source_file, outdir)
    prepared["explanation"] = rewrite_assets(prepared["explanation"], source_file, outdir)
    prepared["material_text"] = rewrite_assets(prepared.get("material_text", ""), source_file, outdir)
    prepared["options"] = [
        dict(option, text=rewrite_assets(option["text"], source_file, outdir))
        for option in prepared["options"]
    ]
    return prepared


def strip_material_heading(text):
    return re.sub(r"^##[ \t\u3000]*材料[ \t\u3000]*\d+[ \t]*\n?", "", text or "").strip()


def display_answer(question):
    answer = question["answer"] or "未标注"
    if not question["options"] and answer in ("A", "B"):
        return "%s（原始答案 %s）" % ("正确" if answer == "A" else "错误", answer)
    return answer


def scope_text(args):
    parts = []
    if args.module:
        parts.append("模块 %s" % args.module)
    if args.year:
        parts.append("年份 %s" % args.year)
    if args.region:
        parts.append("地区 %s" % args.region)
    if args.type:
        parts.append("题型 %s" % args.type)
    if args.keyword:
        parts.append("关键词 %s" % args.keyword)
    return "；".join(parts) if parts else "全库"


def write_outputs(selected, root, outdir, args):
    os.makedirs(outdir, exist_ok=True)
    loaded = load_questions(selected, root)
    prepared = []
    for item in selected:
        question = loaded.get((item["file"], item["qid"]))
        if question:
            prepared.append(prepare_question(question, root, outdir))

    practice_path = os.path.join(outdir, args.name + ".md")
    answer_path = os.path.join(outdir, args.name + "-答案.md")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    practice = [
        "# 行测练习卷",
        "",
        "- 范围：%s" % scope_text(args),
        "- 题量：%d" % len(prepared),
        "- 生成时间：%s" % generated_at,
        "- 答案与解析：`%s`" % os.path.basename(answer_path),
        "",
        "> 题目来自本地 xingcezhenti 题库，qid 用于回查原卷。先做题，再对答案。",
        "",
    ]
    answer_lines = [
        "# 行测练习卷 · 答案与解析",
        "",
        "- 范围：%s" % scope_text(args),
        "- 题量：%d" % len(prepared),
        "- 生成时间：%s" % generated_at,
        "",
    ]

    number = 0
    material_number = 0
    last_material = None
    for question in prepared:
        number += 1
        if question["material_title"]:
            key = question.get("material_key") or (question["file"], question["material_title"])
            if key != last_material:
                material_number += 1
                practice.extend([
                    "## 材料 %d" % material_number,
                    "",
                    strip_material_heading(question["material_text"]),
                    "",
                ])
                last_material = key
            heading = "###"
        else:
            heading = "##"
            last_material = None

        practice.append("%s 第 %d 题（qid %s · %s）" % (
            heading, number, question["qid"], question["type"] or "未标注"))
        practice.append("")
        practice.append(question["stem"])
        practice.append("")
        if question["options"]:
            for option in question["options"]:
                practice.append("- **%s**. %s" % (option["label"], option["text"]))
        else:
            practice.append("（判断题，请直接作答）")
        practice.append("")

        answer_lines.append("## 第 %d 题（qid %s · %s）" % (
            number, question["qid"], question["type"] or "未标注"))
        answer_lines.append("")
        answer_lines.append("- 答案：%s" % display_answer(question))
        answer_lines.append("- 来源：%s（%s %s）" % (
            question["paper"], question["year"], question["region"]))
        answer_lines.append("")
        answer_lines.append(question["explanation"] or "（原题库无解析）")
        answer_lines.append("")

    with open(practice_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(practice).rstrip() + "\n")
    with open(answer_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(answer_lines).rstrip() + "\n")

    return practice_path, answer_path, prepared


def print_stats(items, files, module_counter, elapsed):
    papers = len(set(item["paper"] for item in items if item["paper"]))
    print("题库文件：%d" % files)
    print("不同试卷：%d" % papers)
    print("题目总数：%d" % len(items))
    unique_qids = len(set(item["qid"] for item in items if item["qid"]))
    print("不同 qid：%d" % unique_qids)
    print("重复出现：%d" % (len(items) - unique_qids))
    print("含图题目（题干或解析）：%d" % sum(1 for item in items if item["has_image"]))
    print("带材料题目：%d" % sum(1 for item in items if item["material_title"]))
    print("扫描耗时：%.1fs" % elapsed)
    print("按模块：")
    for module in sorted(module_counter):
        print("  %s %d" % (module, module_counter[module]))
    print("按年份：")
    for year, count in sorted(Counter(item["year"] for item in items).items()):
        print("  %s %d" % (year or "未知", count))
    print("题型 Top 20：")
    for qtype, count in Counter(item["type"] for item in items).most_common(20):
        print("  %s %d" % (qtype or "未标注", count))


def main():
    parser = argparse.ArgumentParser(description="行测题库组卷")
    parser.add_argument("--root", help="xingcezhenti-main 目录；省略时在当前目录及上级查找")
    parser.add_argument("--module", help="模块，如 判断推理、03、资料分析")
    parser.add_argument("--year", help="年份，如 2024、2024,2025、2020-2024")
    parser.add_argument("--region", help="地区，如 四川")
    parser.add_argument("--type", help="题型，如 图形推理、逻辑填空")
    parser.add_argument("--qid", help="按 qid 取题，逗号分隔")
    parser.add_argument("--keyword", help="关键词，匹配题干、选项、解析、试卷名")
    parser.add_argument("--count", type=int, default=20, help="题量，0 表示全部")
    parser.add_argument("--seed", type=int, default=2027, help="随机种子，固定后可复现")
    parser.add_argument("--outdir", default="practice-output", help="输出目录")
    parser.add_argument("--name", default="练习卷", help="输出文件名前缀")
    parser.add_argument("--allow-duplicates", action="store_true",
                        help="保留同一 qid 在不同省份卷中的重复题")
    parser.add_argument("--stats", action="store_true", help="只打印题库统计")
    args = parser.parse_args()

    root = resolve_root(args.root)
    started = time.time()
    items, files, module_counter = scan_bank(root)
    elapsed = time.time() - started

    if args.stats:
        print_stats(items, files, module_counter, elapsed)
        return 0

    pool = filter_items(items, args)
    if args.keyword:
        started = time.time()
        pool = filter_keyword(pool, root, args.keyword)
        elapsed = time.time() - started

    if not pool:
        print("没有符合条件的题目，请放宽 --module/--year/--region/--type/--qid")
        return 1

    if not args.allow_duplicates:
        pool = dedupe_by_qid(pool)

    selected = select_items(pool, args)
    if not selected:
        print("没有选中题目")
        return 1

    outdir = os.path.abspath(args.outdir)
    practice_path, answer_path, prepared = write_outputs(selected, root, outdir, args)

    print("题库：%s" % root)
    print("筛选后题目：%d" % len(pool))
    print("已生成：%d 题" % len(prepared))
    print("练习卷：%s" % practice_path)
    print("答案页：%s" % answer_path)
    if elapsed:
        print("筛选/扫描耗时：%.1fs" % elapsed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
