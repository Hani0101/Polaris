"""Check a design system folder made by the design-system-builder skill.

Usage:
    py check_sync.py design-system/<name>     check one design system
    py check_sync.py --all                    check every folder in ./design-system
    py check_sync.py contrast "#111111" "#ffffff"   print one contrast ratio
    py check_sync.py init design-system/<name>     create the four files from the template

Standard library only. Exits 0 when the design system is complete, 1 otherwise.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED_FILES = ["DESIGN.md", "tokens.json", "banned.md", "CHANGELOG.md"]

REQUIRED_SECTIONS = [
    "## 1. Product context",
    "## 2. Colors",
    "## 3. Typography",
    "## 4. Spacing",
    "## 5. Radius, borders, shadows",
    "## 6. Layout",
    "## 7. Components",
    "## 8. Motion",
    "## 9. Icons and imagery",
    "## 10. Voice and copy",
    "## 11. Banned defaults",
    "## 12. Gap rule",
    "## 13. Do and don't examples",
    "## Open questions",
]

TOKEN_GROUPS = {
    "color", "font", "typography", "space", "radius", "border", "shadow",
    "motion", "layout", "breakpoint", "zIndex", "opacity", "component",
}

GAP_RULES = {"closest-token-and-flag", "stop-and-ask", "mixed"}

# Contrast needed for WCAG AA, by the Kind column of the contrast table.
AA_MINIMUM = {"text": 4.5, "large": 3.0, "ui": 3.0}

TOKEN_REF = re.compile(r"`([A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z0-9]+)+)`")
ALIAS = re.compile(r"^\{([^{}]+)\}$")
TBD = re.compile(r"\bTBD\b")
EM_DASH = "—"


# ---------- markdown parsing ----------

def split_row(line: str) -> list[str]:
    line = line.strip().replace("\\|", "\x00")
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip().replace("\x00", "|") for cell in line.split("|")]


def is_separator(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells if c)


def parse_tables(lines: list[str]) -> list[dict]:
    """Return tables as {heading, header, rows: [(line_no, cells)]}."""
    tables = []
    heading = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        if line.strip().startswith("|"):
            header = [h.lower() for h in split_row(line)]
            rows = []
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_row(lines[i])
                if not is_separator(cells):
                    rows.append((i + 1, cells))
                i += 1
            tables.append({"heading": heading, "header": header, "rows": rows})
            continue
        i += 1
    return tables


def cell(cells: list[str], header: list[str], name: str) -> str | None:
    if name not in header:
        return None
    idx = header.index(name)
    return cells[idx] if idx < len(cells) else ""


# ---------- tokens.json ----------

def flatten(node: dict, prefix: str = "") -> dict[str, dict]:
    out = {}
    for key, value in node.items():
        if key.startswith("$") or not isinstance(value, dict):
            continue
        name = f"{prefix}.{key}" if prefix else key
        if "$value" in value:
            out[name] = value
        out.update(flatten(value, name))
    return out


def resolve(value, tokens: dict[str, dict], seen: set | None = None):
    """Follow {alias} references until a real value is reached."""
    seen = seen or set()
    if isinstance(value, str):
        m = ALIAS.match(value.strip())
        if m:
            target = m.group(1)
            if target in seen or target not in tokens:
                return None
            return resolve(tokens[target]["$value"], tokens, seen | {target})
    return value


def dark_value(token: dict):
    return token.get("$extensions", {}).get("modes", {}).get("dark")


def norm(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
    value = value.strip().strip("`").replace('"', "").replace("'", "")
    return re.sub(r"\s+", " ", value).lower().rstrip(";")


def md_value(raw: str, tokens: dict[str, dict]):
    """A DESIGN.md value cell may hold a literal, `token.name`, or {token.name}."""
    raw = raw.strip()
    m = ALIAS.match(raw) or re.fullmatch(r"`([^`]+)`", raw)
    if m and m.group(1) in tokens:
        return resolve(tokens[m.group(1)]["$value"], tokens)
    return raw


# ---------- contrast ----------

def hex_to_rgb(value) -> tuple[float, float, float] | None:
    if not isinstance(value, str):
        return None
    h = value.strip().lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h[:3])
    elif len(h) in (6, 8):
        h = h[:6]
    else:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None


def luminance(rgb) -> float:
    def channel(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg) -> float | None:
    a, b = hex_to_rgb(fg), hex_to_rgb(bg)
    if a is None or b is None:
        return None
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# ---------- the check ----------

def check(folder: Path) -> bool:
    print(f"=== Design system: {folder.name} ({folder.as_posix()}) ===")
    problems: dict[str, list[str]] = {}

    def add(kind: str, msg: str):
        problems.setdefault(kind, []).append(msg)

    for f in REQUIRED_FILES:
        if not (folder / f).exists():
            add("Missing files", f)

    design_path = folder / "DESIGN.md"
    tokens_path = folder / "tokens.json"
    lines = design_path.read_text(encoding="utf-8").splitlines() if design_path.exists() else []

    tokens: dict[str, dict] = {}
    if tokens_path.exists():
        try:
            tokens = flatten(json.loads(tokens_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            add("tokens.json is not valid JSON", str(e))

    groups = TOKEN_GROUPS | {name.split(".")[0] for name in tokens}

    # Sections present and in order.
    if lines:
        positions = []
        for section in REQUIRED_SECTIONS:
            found = [i for i, l in enumerate(lines) if l.strip() == section]
            if not found:
                add("Missing sections in DESIGN.md", section)
            else:
                positions.append((found[0], section))
        if [s for _, s in positions] != [s for _, s in sorted(positions)]:
            add("Sections out of order in DESIGN.md", "headings must follow the template order")

    tables = parse_tables(lines)

    # Tokens defined in DESIGN.md tables, and value comparison.
    defined: dict[str, int] = {}
    for table in tables:
        header = table["header"]
        if not header or header[0] != "token":
            continue
        for line_no, cells in table["rows"]:
            refs = TOKEN_REF.findall(cells[0])
            if not refs:
                continue
            name = refs[0]
            defined[name] = line_no
            if name.split(".")[0] not in TOKEN_GROUPS:
                add("Unknown token group", f"DESIGN.md:{line_no} `{name}` (allowed: {', '.join(sorted(TOKEN_GROUPS))})")
            if name not in tokens:
                continue
            token = tokens[name]
            for column, json_val in (
                ("value", resolve(token["$value"], tokens)),
                ("light", resolve(token["$value"], tokens)),
                ("dark", resolve(dark_value(token), tokens)),
            ):
                raw = cell(cells, header, column)
                if raw is None:
                    if column == "dark" and dark_value(token) is not None and "light" in header:
                        add("Value mismatches", f"`{name}`: tokens.json has a dark value but DESIGN.md has no Dark column")
                    continue
                md_val = md_value(raw, tokens)
                if "TBD" in (norm(md_val).upper(), norm(json_val).upper()):
                    if norm(md_val) != norm(json_val):
                        add("Value mismatches", f"`{name}` {column}: DESIGN.md says {raw or '(empty)'}, tokens.json says {json_val}")
                    continue
                if isinstance(json_val, (dict, list)):
                    continue  # composite tokens: references are checked below
                if norm(md_val) != norm(json_val):
                    add("Value mismatches", f"`{name}` {column}: DESIGN.md:{line_no} says {raw or '(empty)'}, tokens.json says {json_val}")

    for name, line_no in sorted(defined.items()):
        if name not in tokens:
            add("In DESIGN.md but not in tokens.json", f"`{name}` (DESIGN.md:{line_no})")
    for name in sorted(tokens):
        if name not in defined:
            add("In tokens.json but not in a DESIGN.md token table", f"`{name}`")

    # Every backticked token reference must exist.
    for i, line in enumerate(lines, 1):
        for ref in TOKEN_REF.findall(line):
            if ref.split(".")[0] in groups and ref not in tokens:
                if ref not in defined:  # already reported above
                    add("Unknown token references in DESIGN.md", f"DESIGN.md:{i} `{ref}`")

    # Broken aliases inside tokens.json.
    for name, token in tokens.items():
        values = [token["$value"], dark_value(token)]
        if isinstance(token["$value"], dict):
            values += list(token["$value"].values())
        for v in values:
            if isinstance(v, str) and ALIAS.match(v.strip()) and resolve(v, tokens) is None:
                add("Broken aliases in tokens.json", f"`{name}` -> {v}")

    # Reasons.
    for table in tables:
        header = table["header"]
        if "why" not in header:
            continue
        for line_no, cells in table["rows"]:
            if not cell(cells, header, "why").strip():
                add("Missing why", f"DESIGN.md:{line_no} ({table['heading']})")
    heading = ""
    for i, line in enumerate(lines, 1):
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            continue
        stripped = line.strip()
        if "rules" in heading.lower() and re.match(r"^([-*]|\d+\.)\s", stripped):
            body = re.sub(r"^([-*]|\d+\.)\s+", "", stripped)
            if body != "TBD" and "why:" not in body.lower():
                add("Missing why", f"DESIGN.md:{i} rule without 'Why:' ({heading})")

    # Contrast.
    contrast_lines = []
    for table in tables:
        header = table["header"]
        if "contrast" not in table["heading"].lower() or "text" not in header or "background" not in header:
            continue
        for line_no, cells in table["rows"]:
            fg_ref = TOKEN_REF.findall(cell(cells, header, "text"))
            bg_ref = TOKEN_REF.findall(cell(cells, header, "background"))
            kind = (cell(cells, header, "kind") or "text").strip().lower() or "text"
            need = AA_MINIMUM.get(kind, 4.5)
            if not fg_ref or not bg_ref:
                continue
            fg, bg = fg_ref[0], bg_ref[0]
            if fg not in tokens or bg not in tokens:
                continue
            parts = []
            for mode, getter in (("light", lambda t: t["$value"]), ("dark", dark_value)):
                fv = resolve(getter(tokens[fg]), tokens)
                bv = resolve(getter(tokens[bg]), tokens)
                if fv is None and bv is None and mode == "dark":
                    continue
                if "TBD" in (fv, bv):
                    parts.append(f"{mode}: not decided yet")
                    continue
                ratio = contrast(fv, bv)
                if ratio is None:
                    parts.append(f"{mode}: cannot compute ({fv} on {bv})")
                    continue
                verdict = "PASS" if ratio >= need else "FAIL"
                parts.append(f"{mode} {ratio:.2f}:1 {verdict}")
                if verdict == "FAIL":
                    add("Contrast failures (WCAG AA)", f"`{fg}` on `{bg}` ({kind}, needs {need}:1): {mode} {ratio:.2f}:1")
            contrast_lines.append(f"  `{fg}` on `{bg}` [{kind}, needs {need}:1]: " + "; ".join(parts))

    # banned.md and gap rule.
    banned_path = folder / "banned.md"
    if banned_path.exists():
        banned_tables = parse_tables(banned_path.read_text(encoding="utf-8").splitlines())
        entries = [r for t in banned_tables if "banned" in t["header"] for r in t["rows"]
                   if cell(r[1], t["header"], "banned").strip() not in ("", "TBD")]
        if not entries:
            add("banned.md", "has no banned entries")
    gap = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("Gap rule:")), "")
    if gap not in GAP_RULES:
        add("Gap rule", f"not set (found '{gap or 'nothing'}', expected one of {', '.join(sorted(GAP_RULES))})")
    elif gap != "stop-and-ask":
        flag = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("Flag format:")), "")
        if not flag or flag == "TBD":
            add("Gap rule", "Flag format is not set")

    # TBDs and em dashes in all files.
    # Grouped by file and DESIGN.md section; tokens.json TBDs are named, not line-numbered.
    tbds: dict[str, list[str]] = {}
    for f in REQUIRED_FILES:
        path = folder / f
        if not path.exists():
            continue
        section = f
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if EM_DASH in line:
                add("Em dashes (not allowed)", f"{f}:{i}")
            if f == "DESIGN.md" and line.startswith("## "):
                section = line[3:].strip()
            if f != "tokens.json" and TBD.search(line) and section != "Open questions":
                tbds.setdefault(section, []).append(f"{f}:{i}: {line.strip()[:100]}")
    for name, token in tokens.items():
        modes = [m for m, v in (("value", token["$value"]), ("dark", dark_value(token))) if v == "TBD"]
        if modes:
            tbds.setdefault("tokens.json", []).append(f"`{name}` ({', '.join(modes)})")

    # Report.
    if contrast_lines:
        print("\nContrast (section 2.2):")
        print("\n".join(contrast_lines))
    for kind, msgs in problems.items():
        print(f"\n{kind} ({len(msgs)}):")
        for m in msgs:
            print(f"  - {m}")
    total = sum(len(v) for v in tbds.values())
    print(f"\nTBDs remaining ({total}):")
    for section, items in tbds.items():
        print(f"  [{section}] ({len(items)})")
        for t in items:
            print(f"    - {t}")

    complete = not problems and not tbds
    print(f"\nResult: {'COMPLETE' if complete else 'NOT COMPLETE'}\n")
    return complete


# ---------- init ----------

TEMPLATE = Path(__file__).resolve().parent.parent / "references" / "doc-template.md"


def token_type(name: str) -> str:
    parts = name.split(".")
    if parts[0] in ("color", "typography", "shadow"):
        return parts[0]
    if parts[0] == "zIndex" or name == "layout.grid.columns":
        return "number"
    if parts[0] == "font":
        return {"family": "fontFamily", "weight": "fontWeight", "lineHeight": "number"}.get(parts[1], "dimension")
    if parts[0] == "motion":
        return "duration" if parts[1] == "duration" else "cubicBezier"
    return "dimension"


def init(folder: Path) -> int:
    if folder.exists() and any(folder.iterdir()):
        print(f"{folder} already has files. Use Continue mode instead of init.")
        return 2
    from datetime import date
    today = date.today().isoformat()
    name = folder.name
    blocks = re.findall(r"^```markdown\n(.*?)^```$", TEMPLATE.read_text(encoding="utf-8"), re.S | re.M)
    design, banned, changelog = blocks[0], blocks[1], blocks[2]

    design = design.replace("<name>", name).replace("<YYYY-MM-DD>", today)
    banned = re.sub(r"\n\| Purple.*\n", "\n", banned.replace("<name>", name))
    changelog = re.sub(r"\d{4}-\d{2}-\d{2}", today, changelog.replace("<name>", name))

    tokens: dict = {}
    for table in parse_tables(design.splitlines()):
        if not table["header"] or table["header"][0] != "token":
            continue
        for _, cells in table["rows"]:
            refs = TOKEN_REF.findall(cells[0])
            if not refs:
                continue
            node = tokens
            for part in refs[0].split("."):
                node = node.setdefault(part, {})
            node["$type"] = token_type(refs[0])
            node["$value"] = "TBD"
            if "dark" in table["header"]:
                node["$extensions"] = {"modes": {"dark": "TBD"}}

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "DESIGN.md").write_text(design, encoding="utf-8")
    (folder / "banned.md").write_text(banned, encoding="utf-8")
    (folder / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    (folder / "tokens.json").write_text(json.dumps(tokens, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Created {folder} with DESIGN.md, tokens.json, banned.md, CHANGELOG.md")
    return 0


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    if len(argv) == 2 and argv[0] == "init":
        return init(Path(argv[1]))

    if len(argv) == 3 and argv[0] == "contrast":
        ratio = contrast(argv[1], argv[2])
        if ratio is None:
            print("Give two hex colors, like #1a1a1a #ffffff")
            return 2
        checks = ", ".join(f"{k} {'PASS' if ratio >= v else 'FAIL'}" for k, v in AA_MINIMUM.items())
        print(f"{ratio:.2f}:1 ({checks})")
        return 0

    if argv == ["--all"]:
        root = Path("design-system")
        folders = sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []
        if not folders:
            print("No design systems found in ./design-system")
            return 1
    elif len(argv) == 1:
        folders = [Path(argv[0])]
        if not folders[0].is_dir():
            print(f"Not a folder: {folders[0]}")
            return 2
    else:
        print(__doc__)
        return 2

    results = [check(f) for f in folders]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
