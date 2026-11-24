#!/usr/bin/env python3
"""Split static/app.js into BookPup namespace modules (one-time refactor helper)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "static" / "app.js"

# Inclusive 1-based line ranges (inside the IIFE) per output file.
SPLITS: dict[str, list[tuple[int, int]]] = {
    "app-core.js": [
        (4, 317),
        (686, 727),
        (778, 838),
        (2146, 2193),
    ],
    "app-docs.js": [(729, 776), (1135, 1400)],
    "app-irc.js": [(318, 389), (418, 679)],
    "app-account.js": [(840, 1134)],
    "app-search.js": [(390, 417), (681, 684), (1402, 2064), (2311, 2495)],
    "app-queue.js": [(2065, 2309), (2497, 2630)],
    "app-library.js": [(2632, 3970)],
    "app-boot.js": [(3972, 4012)],
}

CORE_HEADER = """window.BookPup = window.BookPup || {};
(function (BP) {
  "use strict";
  BP.CSRF = { "X-Bookpup": "1" };
  BP.COVER_MAX_BYTES = 2 * 1024 * 1024;
  BP.state = {
    authHeader: null,
    sessionAdmin: false,
    sessionUsername: "",
    sessionOpdsUrl: "",
    notifiedDoneJobs: new Set(),
    coverImageSearchEnabled: false,
    activeSearchJob: null,
    activeDownloadJob: null,
    activeDownloadTitle: "",
    pollTimer: null,
    sendTarget: null,
    ircEvents: [],
    ircAfterId: 0,
  };
"""

MODULE_HEADER = """(function (BP) {
  "use strict";
  const CSRF = BP.CSRF;
  const COVER_MAX_BYTES = BP.COVER_MAX_BYTES;
"""

MODULE_FOOTER = """
})(window.BookPup);
"""

STATE_DECL = re.compile(
    r"^\s+(?:let|const)\s+(?:"
    + "|".join(
        (
            "authHeader",
            "sessionAdmin",
            "sessionUsername",
            "sessionOpdsUrl",
            "notifiedDoneJobs",
            "coverImageSearchEnabled",
            "activeSearchJob",
            "activeDownloadJob",
            "activeDownloadTitle",
            "pollTimer",
            "sendTarget",
            "ircEvents",
            "ircAfterId",
        )
    )
    + r")\b"
)

STATE_VARS = frozenset(
    {
        "authHeader",
        "sessionAdmin",
        "sessionUsername",
        "sessionOpdsUrl",
        "notifiedDoneJobs",
        "coverImageSearchEnabled",
        "activeSearchJob",
        "activeDownloadJob",
        "activeDownloadTitle",
        "pollTimer",
        "sendTarget",
        "ircEvents",
        "ircAfterId",
    }
)

FN_DEF = re.compile(r"^\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
EXPORT_SKIP = frozenset({"if", "for", "while", "switch", "catch"})


def read_lines() -> list[str]:
    text = SRC.read_text(encoding="utf-8")
    if not text.startswith("(function"):
        raise SystemExit("unexpected app.js wrapper")
    return text.splitlines()


def extract_ranges(lines: list[str], ranges: list[tuple[int, int]]) -> list[str]:
    out: list[str] = []
    for start, end in ranges:
        chunk = lines[start - 1 : end]
        out.extend(chunk)
        out.append("")
    return out


def find_functions(body: str) -> set[str]:
    found: set[str] = set()
    for line in body.splitlines():
        m = FN_DEF.match(line)
        if m:
            name = m.group(1)
            if name not in EXPORT_SKIP:
                found.add(name)
    return found


def strip_state_decls(body: str) -> str:
    lines = []
    for line in body.splitlines():
        if STATE_DECL.match(line):
            continue
        if line.strip() == 'const CSRF = { "X-Bookpup": "1" };':
            continue
        if line.strip() == "const COVER_MAX_BYTES = 2 * 1024 * 1024;":
            continue
        lines.append(line)
    return "\n".join(lines)


def state_var_rewrite(body: str) -> str:
    for name in sorted(STATE_VARS, key=len, reverse=True):
        body = re.sub(rf"(?<![.\w]){name}\b(?!\s*:)", f"BP.state.{name}", body)
    return body


def patch_cross_calls(body: str, local: set[str], exported: set[str]) -> str:
    for fn in sorted(exported - local, key=len, reverse=True):
        body = re.sub(rf"(?<![.\w]){fn}\s*\(", f"BP.{fn}(", body)
    return body


def build_exports(local: set[str]) -> str:
    lines = ["  // exports"]
    for fn in sorted(local):
        lines.append(f"  BP.{fn} = {fn};")
    return "\n".join(lines)


def assemble_core(body: str, local: set[str], all_exported: set[str]) -> str:
    body = strip_state_decls(body)
    body = state_var_rewrite(body)
    body = patch_cross_calls(body, local, all_exported)
    exports = build_exports(local)
    return CORE_HEADER + body + "\n" + exports + "\n})(window.BookPup);\n"


def assemble_module(body: str, local: set[str], all_exported: set[str]) -> str:
    body = strip_state_decls(body)
    body = state_var_rewrite(body)
    body = patch_cross_calls(body, local, all_exported)
    exports = build_exports(local)
    return MODULE_HEADER + body + "\n" + exports + MODULE_FOOTER


def main() -> None:
    lines = read_lines()
    bodies: dict[str, str] = {}
    locals_by_file: dict[str, set[str]] = {}

    for fname, ranges in SPLITS.items():
        raw = "\n".join(extract_ranges(lines, ranges))
        bodies[fname] = raw
        locals_by_file[fname] = find_functions(raw)

    all_exported: set[str] = set()
    for s in locals_by_file.values():
        all_exported |= s

    out_dir = ROOT / "static"
    for fname, body in bodies.items():
        local = locals_by_file[fname]
        if fname == "app-core.js":
            content = assemble_core(body, local, all_exported)
        else:
            content = assemble_module(body, local, all_exported)
        (out_dir / fname).write_text(content, encoding="utf-8")
        print(f"wrote {fname} ({len(content.splitlines())} lines)")


if __name__ == "__main__":
    main()