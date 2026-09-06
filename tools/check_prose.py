#!/usr/bin/env python3
"""Prose conventions for the Markdown in this repo.

Two rules, both American-English house style:

  1. No em dash inside a sentence. Recast with a comma, colon, parentheses or a
     full stop. An em dash used as a *list separator* is fine and is the
     established format here, so "- **Videos** - gloss" and table rows are
     allowed; the ban is on the character standing in for punctuation mid-sentence.
  2. American spellings.

Exit code 0 if clean, 1 otherwise.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EM = "—"

BRITISH = re.compile(
    r"\b(behaviour|colour|organis[ei]\w*|recognis\w*|modelling|labelled|whilst|"
    r"defence|licence|practise|centre|analyse|normalis[ei]\w*|optimis[ei]\w*|"
    r"minimis[ei]\w*|summaris[ei]\w*|visualis[ei]\w*|initialis[ei]\w*|"
    r"favourite|emphasis[ei]\w*)\b", re.I)

# "- item - gloss" and "- [Title](link) - hook": the separator format, allowed
LIST_GLOSS = re.compile(rf"^\s*[-*]\s.*?\s{EM}\s")
TABLE_ROW = re.compile(r"^\s*\|")


def main():
    problems = []
    for path in sorted(ROOT.glob("*.md")) + sorted(ROOT.glob("*/*.md")):
        if ".github" in path.parts:
            continue
        in_code = False
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            rel = path.relative_to(ROOT)
            if EM in line and not LIST_GLOSS.match(line) and not TABLE_ROW.match(line):
                problems.append(f"{rel}:{n}: em dash inside a sentence\n    {line.strip()[:96]}")
            m = BRITISH.search(line)
            if m:
                problems.append(f"{rel}:{n}: British spelling {m.group(0)!r}\n    {line.strip()[:96]}")

    if problems:
        print(f"{len(problems)} prose issue(s):\n")
        for p in problems:
            print(p)
        return 1
    print("prose ok: no mid-sentence em dashes, no British spellings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
