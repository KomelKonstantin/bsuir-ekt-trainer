#!/usr/bin/env python3
"""Собирает index.html из app-template.html и data/topic-*.json (формат — в SPEC.md).

Запуск:
    python3 build.py            # реальные данные: data/topic-*.json
    python3 build.py --sample   # тестовые данные: data/_sample/topic-*.json

Кроме index.html копирует source/konspekt.html и source/formulas.html в корень.
"""
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
SAMPLE = DATA / "_sample"
TEMPLATE = ROOT / "app-template.html"
OUT = ROOT / "index.html"
MARKER = "/*__TOPICS__*/[]"
COPIES = (("source/konspekt.html", "konspekt.html"),
          ("source/formulas.html", "formulas.html"))

SECTIONS = ("Лекции", "Эволюция мысли", "Шпаргалки")
RANGES = {"Лекции": (1, 19), "Эволюция мысли": (20, 39), "Шпаргалки": (40, 59)}

STR, NUM = "строка", "число"
# поле -> (описание кортежа, типы элементов, сколько первых элементов обязаны быть непустыми)
TUPLES = {
    "cards":     ("[термин, определение, тег]", (STR, STR, STR), 2),
    "authors":   ("[автор, труд или идея, школа]", (STR, STR, STR), 2),
    "chrono":    ("[событие, период/год, число для сортировки]", (STR, STR, NUM), 1),
    "pairs":     ("[понятие A, понятие B, чем отличаются]", (STR, STR, STR), 3),
    "formulas":  ("[название, формула, расшифровка]", (STR, STR, STR), 2),
    "questions": ("[вопрос, ответ]", (STR, STR), 2),
}
KNOWN_KEYS = {"n", "title", "section", "lists", *TUPLES}


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_type(v, t):
    return isinstance(v, str) if t == STR else is_num(v)


def validate(d, name, check_range=True):
    """Возвращает (ошибки, предупреждения)."""
    err, warn = [], []
    if not isinstance(d, dict):
        return [f"{name}: верхний уровень должен быть объектом {{...}}"], warn

    for k in ("n", "title", "section"):
        if k not in d:
            err.append(f"{name}: нет обязательного поля «{k}»")
    if "n" in d and not (isinstance(d["n"], int) and not isinstance(d["n"], bool)):
        err.append(f"{name}: «n» должно быть целым числом, сейчас {d['n']!r}")
    if "title" in d and (not isinstance(d["title"], str) or not d["title"].strip()):
        err.append(f"{name}: «title» должно быть непустой строкой")
    if "section" in d and d["section"] not in SECTIONS:
        err.append(f"{name}: «section» = {d.get('section')!r}, допустимо: {', '.join(SECTIONS)}")
    if check_range and not err and d["section"] in RANGES:
        lo, hi = RANGES[d["section"]]
        if not lo <= d["n"] <= hi:
            warn.append(f"{name}: n={d['n']} вне диапазона {lo}–{hi} для раздела «{d['section']}»")

    for k in d:
        if k not in KNOWN_KEYS:
            warn.append(f"{name}: неизвестное поле «{k}» — будет проигнорировано")

    for field, (shape, types, nonempty) in TUPLES.items():
        if field not in d:
            continue
        arr = d[field]
        if not isinstance(arr, list):
            err.append(f"{name}: «{field}» должно быть массивом")
            continue
        for i, row in enumerate(arr):
            where = f"{name}: {field}[{i}]"
            if not isinstance(row, list) or len(row) != len(types):
                err.append(f"{where}: ожидается {shape} ({len(types)} эл.), сейчас {json.dumps(row, ensure_ascii=False)[:120]}")
                continue
            for j, (v, t) in enumerate(zip(row, types)):
                if not check_type(v, t):
                    err.append(f"{where}[{j}]: ожидается {t}, сейчас {v!r}"[:200])
                elif t == STR and j < nonempty and not v.strip():
                    err.append(f"{where}[{j}]: пустая строка")

    if "lists" in d:
        arr = d["lists"]
        if not isinstance(arr, list):
            err.append(f"{name}: «lists» должно быть массивом")
        else:
            for i, row in enumerate(arr):
                where = f"{name}: lists[{i}]"
                if not isinstance(row, dict):
                    err.append(f"{where}: ожидается объект {{\"q\": ..., \"items\": [...]}}")
                    continue
                if not isinstance(row.get("q"), str) or not row["q"].strip():
                    err.append(f"{where}: «q» должно быть непустой строкой")
                items = row.get("items")
                if not isinstance(items, list) or len(items) < 2:
                    err.append(f"{where}: «items» должно быть массивом минимум из 2 строк")
                elif not all(isinstance(x, str) and x.strip() for x in items):
                    err.append(f"{where}: все «items» должны быть непустыми строками")
    return err, warn


def load_topics(folder):
    paths = sorted(folder.glob("topic-*.json"))
    if not paths:
        sys.exit(f"В {folder.relative_to(ROOT)}/ нет файлов topic-*.json"
                 + ("" if folder == SAMPLE else " (для тестовых данных: python3 build.py --sample)"))
    topics, errors, warnings, seen = [], [], [], {}
    for path in paths:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{path.name}: не JSON — строка {e.lineno}, столбец {e.colno}: {e.msg}")
            continue
        err, warn = validate(d, path.name, check_range=folder != SAMPLE)
        errors += err
        warnings += warn
        if err:
            continue
        if d["n"] in seen:
            errors.append(f"{path.name}: n={d['n']} уже занят файлом {seen[d['n']]}")
            continue
        seen[d["n"]] = path.name
        topic = {k: d[k] for k in d if k in KNOWN_KEYS}
        topics.append(topic)
    for w in warnings:
        print("ВНИМАНИЕ:", w, file=sys.stderr)
    if errors:
        print(f"Ошибки в данных ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print("  ✗", e, file=sys.stderr)
        sys.exit(1)
    topics.sort(key=lambda t: t["n"])
    return topics


def main(argv):
    unknown = [a for a in argv if a != "--sample"]
    if unknown:
        sys.exit(f"Неизвестные аргументы: {' '.join(unknown)}. Использование: python3 build.py [--sample]")
    folder = SAMPLE if "--sample" in argv else DATA
    topics = load_topics(folder)

    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(MARKER) != 1:
        sys.exit(f"В шаблоне должна быть ровно одна метка {MARKER}")
    payload = json.dumps(topics, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")  # чтобы текст не закрыл <script>
    OUT.write_text(template.replace(MARKER, payload), encoding="utf-8")

    for src, dst in COPIES:
        s = ROOT / src
        if s.exists():
            shutil.copyfile(s, ROOT / dst)
        else:
            print(f"ВНИМАНИЕ: нет {src} — {dst} не обновлён", file=sys.stderr)

    print(f"index.html собран из {folder.relative_to(ROOT)}/: {len(topics)} {plural(len(topics), 'тема', 'темы', 'тем')}, "
          f"{OUT.stat().st_size // 1024} КБ")
    fields = ["cards", "authors", "lists", "chrono", "pairs", "formulas", "questions"]
    for t in topics:
        counts = ", ".join(f"{f} {len(t[f])}" for f in fields if t.get(f))
        print(f"  {t['n']:>2}. [{t['section']}] {t['title']} — {counts or 'нет данных'}")


if __name__ == "__main__":
    main(sys.argv[1:])
