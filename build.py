#!/usr/bin/env python3
"""Собирает index.html из app-template.html и data/lesson-*.json.

Запуск:  python3 build.py
Добавить урок: положить в data/ новый lesson-NN.json того же формата и пересобрать.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
TEMPLATE = ROOT / "app-template.html"
OUT = ROOT / "index.html"
MARKER = "/*__LESSONS__*/[]"

REQUIRED = ("n", "module", "title", "titleRu", "page", "entries")


def load_lessons():
    lessons = []
    for path in sorted(DATA.glob("lesson-*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        missing = [k for k in REQUIRED if k not in d]
        if missing:
            sys.exit(f"{path.name}: нет полей {', '.join(missing)}")
        for i, e in enumerate(d["entries"]):
            if len(e) != 3 or not e[0] or not e[1]:
                sys.exit(f"{path.name}: запись {i} должна быть [англ, рус, часть речи]")
        lessons.append(d)
    if not lessons:
        sys.exit("В data/ нет файлов lesson-*.json")
    lessons.sort(key=lambda d: d["n"])
    return lessons


def main():
    lessons = load_lessons()
    template = TEMPLATE.read_text(encoding="utf-8")
    if MARKER not in template:
        sys.exit(f"В шаблоне нет метки {MARKER}")

    payload = json.dumps(lessons, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(template.replace(MARKER, payload), encoding="utf-8")

    total = sum(len(d["entries"]) for d in lessons)
    print(f"index.html собран: {len(lessons)} уроков, {total} слов, "
          f"{OUT.stat().st_size // 1024} КБ")
    for d in lessons:
        print(f"  {d['n']:>2}. {d['title']} — {len(d['entries'])}")


if __name__ == "__main__":
    main()
