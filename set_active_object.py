"""Rewrite lift.py so exactly one `self.cube = ...` definition is active.

Usage:
  python set_active_object.py --ycb <ycb_id>            # YCB object
  python set_active_object.py --xml <ClassName>         # e.g. BottleObject
  python set_active_object.py --primitive <ClassName>   # e.g. BoxObject

This is a generalization of set_active_ycb.py that also understands the
single-line XML objects (BottleObject, CanObject, ...) and the multi-line
primitive objects (BoxObject, CylinderObject, CapsuleObject, BallObject).
Comments out every other matching `self.cube = ...` line/block and uncomments
the target. Preserves any `##` double-commented lines as-is.
"""
import re
import sys
import argparse
from pathlib import Path

LIFT_PY = Path(__file__).parent / "environments" / "manipulation" / "lift.py"

YCB_RE = re.compile(
    r'^(?P<indent>\s*)(?P<comment>#+ )?'
    r'(?P<body>self\.cube = YCBObject\(name="cube", ycb_id="(?P<id>[^"]+)"\))\s*$'
)
XML_RE = re.compile(
    r'^(?P<indent>\s*)(?P<comment>#+ )?'
    r'(?P<body>self\.cube = (?P<cls>Bottle|Can|Lemon|Milk|Bread|Cereal)Object'
    r'\(name="cube"\))\s*$'
)
PRIM_START_RE = re.compile(
    r'^(?P<indent>\s*)(?P<comment>#+ )?'
    r'self\.cube = (?P<cls>Box|Cylinder|Capsule|Ball)Object\(\s*$'
)
# Closing `)` on its own line (possibly preceded by `# `). We deliberately
# anchor `^...\)\s*$` so we do NOT match lines like
# `# size_max=[0.022, 0.022, 0.022],  # [0.018, 0.018, 0.018])` where `)` is
# the tail of an inline comment.
PRIM_END_RE = re.compile(r'^(?P<indent>\s*)(?P<comment>#+ )?\)\s*$')


def is_double(comment):
    return bool(comment) and comment.startswith("##")


def is_commented(line):
    """True if the first non-whitespace character on the line is '#'."""
    return bool(re.match(r'^\s*#', line))


def add_comment(line):
    """Prepend '# ' to the content after indent (assumes line is uncommented)."""
    m = re.match(r'^(?P<indent>\s*)(?P<rest>.*)$', line.rstrip("\n"))
    return f"{m.group('indent')}# {m.group('rest')}\n"


def strip_comment(line):
    """Strip a single leading '# ' after indent (assumes line is single-commented)."""
    m = re.match(r'^(?P<indent>\s*)# (?P<rest>.*)$', line.rstrip("\n"))
    if not m:
        # Already uncommented (or some weird shape); return as-is.
        return line if line.endswith("\n") else line + "\n"
    return f"{m.group('indent')}{m.group('rest')}\n"


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ycb", metavar="YCB_ID",
                   help="Activate YCBObject with this ycb_id (e.g. 002_master_chef_can).")
    g.add_argument("--xml", metavar="CLASS_NAME",
                   help="Activate XML object by class name (e.g. BottleObject).")
    g.add_argument("--primitive", metavar="CLASS_NAME",
                   help="Activate primitive object by class name (e.g. BoxObject).")
    args = ap.parse_args()

    if args.ycb:
        target_kind, target_value = "ycb", args.ycb
    elif args.xml:
        target_kind, target_value = "xml", args.xml
    else:
        target_kind, target_value = "primitive", args.primitive

    src = LIFT_PY.read_text().splitlines(keepends=True)
    out = []
    found = False
    i = 0
    while i < len(src):
        line = src[i]
        bare = line.rstrip("\n")

        # ---- primitive block (multi-line) ----
        m_prim = PRIM_START_RE.match(bare)
        if m_prim and not is_double(m_prim.group("comment")):
            cls = m_prim.group("cls") + "Object"
            block = [line]
            j = i + 1
            while j < len(src):
                block.append(src[j])
                m_end = PRIM_END_RE.match(src[j].rstrip("\n"))
                if m_end and not is_double(m_end.group("comment")):
                    break
                j += 1
            is_target = (target_kind == "primitive" and cls == target_value)
            if is_target:
                for bl in block:
                    out.append(strip_comment(bl) if is_commented(bl) else bl)
                found = True
            else:
                for bl in block:
                    out.append(bl if is_commented(bl) else add_comment(bl))
            i = j + 1
            continue

        # ---- YCB single-line ----
        m_ycb = YCB_RE.match(bare)
        if m_ycb and not is_double(m_ycb.group("comment")):
            indent = m_ycb.group("indent")
            body = m_ycb.group("body")
            ycb_id = m_ycb.group("id")
            is_target = (target_kind == "ycb" and ycb_id == target_value)
            out.append(f"{indent}{body}\n" if is_target else f"{indent}# {body}\n")
            if is_target:
                found = True
            i += 1
            continue

        # ---- XML single-line ----
        m_xml = XML_RE.match(bare)
        if m_xml and not is_double(m_xml.group("comment")):
            indent = m_xml.group("indent")
            body = m_xml.group("body")
            cls = m_xml.group("cls") + "Object"
            is_target = (target_kind == "xml" and cls == target_value)
            out.append(f"{indent}{body}\n" if is_target else f"{indent}# {body}\n")
            if is_target:
                found = True
            i += 1
            continue

        out.append(line)
        i += 1

    if not found:
        print(f"error: target {target_kind}={target_value!r} not found in {LIFT_PY}",
              file=sys.stderr)
        sys.exit(1)

    LIFT_PY.write_text("".join(out))
    print(f"activated {target_kind}={target_value}")


if __name__ == "__main__":
    main()
