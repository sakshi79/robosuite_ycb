"""Rewrite lift.py so exactly one YCB self.cube line is active.

Usage: python set_active_ycb.py <ycb_id>

Comments out every `self.cube = ...` line in the YCB block (single `#`),
preserves any `##` double-comment lines as-is, and uncomments only the line
whose ycb_id matches the argument.
"""
import re
import sys
from pathlib import Path

LIFT_PY = Path(__file__).parent / "environments" / "manipulation" / "lift.py"

YCB_LINE_RE = re.compile(
    r'^(?P<indent>\s*)(?P<comment>#+ )?self\.cube = YCBObject\(name="cube", ycb_id="(?P<id>[^"]+)"\)\s*$'
)


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <ycb_id>", file=sys.stderr)
        sys.exit(2)
    target = sys.argv[1]

    src = LIFT_PY.read_text().splitlines(keepends=True)
    out = []
    found = False
    for line in src:
        m = YCB_LINE_RE.match(line.rstrip("\n"))
        if not m:
            out.append(line)
            continue
        comment = m.group("comment") or ""
        # Leave double-commented (##) lines untouched.
        if comment.startswith("## "):
            out.append(line)
            continue
        indent = m.group("indent")
        ycb_id = m.group("id")
        body = f'self.cube = YCBObject(name="cube", ycb_id="{ycb_id}")'
        if ycb_id == target:
            out.append(f"{indent}{body}\n")
            found = True
        else:
            out.append(f"{indent}# {body}\n")

    if not found:
        print(f"error: ycb_id {target!r} not found in {LIFT_PY}", file=sys.stderr)
        sys.exit(1)

    LIFT_PY.write_text("".join(out))
    print(f"activated {target}")


if __name__ == "__main__":
    main()
