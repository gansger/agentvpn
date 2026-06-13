"""Parse project Python files without writing bytecode into the workspace."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = (ROOT / "apps", ROOT / "infrastructure", ROOT / "packages", ROOT / "tests")


def main() -> int:
    failures: list[str] = []
    checked = 0

    for source_root in SOURCE_ROOTS:
        for path in source_root.rglob("*.py"):
            checked += 1
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError, UnicodeError) as exc:
                failures.append(f"{path.relative_to(ROOT)}: {exc}")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1

    print(f"Syntax OK: {checked} Python files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
