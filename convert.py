#!/usr/bin/env python3
"""Convert between the nested JSON5 format and flat CSV format for question files."""

import argparse
import csv
import json
import sys
from collections import OrderedDict
from pathlib import Path

import json5


def _load_json(path: Path):
    loader = json5 if path.suffix.lower() == ".json5" else json
    with path.open(encoding="utf-8") as f:
        return loader.load(f)


def _dump_json(data, path: Path) -> None:
    dumper = json5 if path.suffix.lower() == ".json5" else json
    with path.open("w", encoding="utf-8") as f:
        dumper.dump(data, f, indent=2, ensure_ascii=False)

MAX_OPTIONS = 6
CSV_FIELDS = [
    "course_name", "module_name", "submodule_name",
    "description", "explanation", "level", "mode", "max_score",
    *[f"option{i}_{k}" for i in range(1, MAX_OPTIONS + 1) for k in ("text", "quality", "feedback")],
]


def csv_to_json5(src: Path, dst: Path) -> None:
    with src.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    courses: OrderedDict = OrderedDict()
    for row in rows:
        course = row["course_name"].strip()
        module = row["module_name"].strip()
        submodule = row["submodule_name"].strip()

        level = row["level"].strip()
        max_score = row["max_score"].strip()
        question = {
            "description": row["description"].strip(),
            "explanation": row["explanation"].strip(),
            "level": int(level) if level else None,
            "mode": row["mode"].strip(),
            "max_score": int(max_score) if max_score else None,
            "options": [],
        }
        for i in range(1, MAX_OPTIONS + 1):
            text = row.get(f"option{i}_text", "").strip()
            if text:
                question["options"].append({
                    "text": text,
                    "quality": row.get(f"option{i}_quality", "").strip(),
                    "feedback": row.get(f"option{i}_feedback", "").strip(),
                })

        courses.setdefault(course, OrderedDict())
        courses[course].setdefault(module, OrderedDict())
        courses[course][module].setdefault(submodule, [])
        courses[course][module][submodule].append(question)

    output = [
        {
            "course": course,
            "modules": [
                {
                    "module": module,
                    "submodules": [
                        {"submodule": submodule, "questions": qs}
                        for submodule, qs in submodules.items()
                    ],
                }
                for module, submodules in modules.items()
            ],
        }
        for course, modules in courses.items()
    ]

    _dump_json(output, dst)

    total = sum(
        len(sub["questions"])
        for c in output
        for m in c["modules"]
        for sub in m["submodules"]
    )
    print(f"csv → json5: {len(output)} course(s), {total} questions → {dst}")


def json5_to_csv(src: Path, dst: Path) -> None:
    data = _load_json(src)

    rows = []
    for course_obj in data:
        course = course_obj["course"]
        for module_obj in course_obj["modules"]:
            module = module_obj["module"]
            for sub_obj in module_obj["submodules"]:
                submodule = sub_obj["submodule"]
                for q in sub_obj["questions"]:
                    row = {
                        "course_name": course,
                        "module_name": module,
                        "submodule_name": submodule,
                        "description": q.get("description", ""),
                        "explanation": q.get("explanation", ""),
                        "level": q.get("level", ""),
                        "mode": q.get("mode", ""),
                        "max_score": q.get("max_score", "") or "",
                    }
                    options = q.get("options", [])
                    for i, opt in enumerate(options[:MAX_OPTIONS], start=1):
                        row[f"option{i}_text"] = opt.get("text", "")
                        row[f"option{i}_quality"] = opt.get("quality", "")
                        row[f"option{i}_feedback"] = opt.get("feedback", "")
                    # Fill remaining option slots with empty strings
                    for i in range(len(options) + 1, MAX_OPTIONS + 1):
                        row[f"option{i}_text"] = ""
                        row[f"option{i}_quality"] = ""
                        row[f"option{i}_feedback"] = ""
                    rows.append(row)

    with dst.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"json5 → csv: {len(rows)} questions → {dst}")


def detect_and_convert(src: Path, dst: Path) -> None:
    src_ext = src.suffix.lower()
    dst_ext = dst.suffix.lower()

    if src_ext == ".csv" and dst_ext in (".json5", ".json"):
        csv_to_json5(src, dst)
    elif src_ext in (".json5", ".json") and dst_ext == ".csv":
        json5_to_csv(src, dst)
    else:
        sys.exit(
            f"Cannot determine conversion direction from '{src_ext}' to '{dst_ext}'.\n"
            "Supported pairs: .csv → .json5  |  .json5 → .csv"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert question files between nested JSON5 and flat CSV."
    )
    parser.add_argument("source", type=Path, help="Input file (.csv or .json5)")
    parser.add_argument("dest", type=Path, help="Output file (.json5 or .csv)")
    args = parser.parse_args()

    if not args.source.exists():
        sys.exit(f"Source file not found: {args.source}")

    detect_and_convert(args.source, args.dest)


if __name__ == "__main__":
    main()
