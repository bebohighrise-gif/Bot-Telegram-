#!/usr/bin/env python3
"""OnlyFans_ManagerBot V9 entry — assembles parts and runs infinity_polling."""
from pathlib import Path
import sys

base = Path(__file__).resolve().parent
parts = []
for i in range(4):
    p = base / f"part{i}.py.txt"
    if not p.exists():
        print(f"ERROR: missing {p.name}", file=sys.stderr)
        sys.exit(1)
    parts.append(p.read_text(encoding="utf-8"))

code = "".join(parts)
# Execute as __main__ so handlers register and polling starts
exec(compile(code, str(base / "bot_assembled.py"), "exec"), {"__name__": "__main__", "__file__": str(base / "main.py")})
