"""Cheap geometry invariants for a reconstruction — RUN THIS BEFORE export_viz.

The expensive stages (export_viz -> GLBs + assembly STEPs, make_animation ->
dozens of rendered frames) take minutes. Every defect they surface is a defect
that a few seconds of boolean algebra could have surfaced first. This script is
that first pass.

Three checks, in decreasing order of "always a bug":

  1. LOOSE PARTS      — a child that is not exactly one solid: a boolean that
                        silently did not fuse (`a + b` fuses only when the shapes
                        overlap) or a cut that severed the body. ALWAYS a bug.
  2. WALL PENETRATION — with --shell LABEL, any occurrence sharing volume with a
                        housing. A shaft through a properly-bored wall does NOT
                        intersect it, so a hit here means a missing bore or an
                        undersized case. Almost always a bug.
  3. INTERFERENCE     — any other pair sharing volume, ranked. Some of this is by
                        design (a spline engaging its sleeve, a gear on its hub,
                        a bearing pressed into a bore) so it is reported for
                        review, and only fails under --strict. Meshing gear teeth
                        that clash show up here — that IS a bug.

Usage:
    python check_model.py mymodel.py
    python check_model.py mymodel.py --shell transmission_case --shell rear_extension
    python check_model.py mymodel.py --strict --ignore hub:sleeve --ignore shaft:gear

Whitelist by-design overlaps with --ignore A:B (substring match on both labels)
rather than raising --max-overlap, which would blind you to real clashes.
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import os
import sys


def _load(path):
    spec = importlib.util.spec_from_file_location("model_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    spec.loader.exec_module(mod)
    return mod


def _bbox_overlap_volume(a, b):
    """Volume shared by two bounding boxes.

    The true solid intersection can never exceed this, so it is a sound cheap
    reject: skip the (expensive) boolean whenever this is already below the
    tolerance.
    """
    ba, bb = a.bounding_box(), b.bounding_box()
    dx = min(ba.max.X, bb.max.X) - max(ba.min.X, bb.min.X)
    dy = min(ba.max.Y, bb.max.Y) - max(ba.min.Y, bb.min.Y)
    dz = min(ba.max.Z, bb.max.Z) - max(ba.min.Z, bb.min.Z)
    if dx <= 0 or dy <= 0 or dz <= 0:
        return 0.0
    return dx * dy * dz


def _shared_volume(a, b):
    try:
        inter = a & b
    except Exception:
        return 0.0
    return getattr(inter, "volume", 0.0) if inter is not None else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", help="python file exposing gen_step()")
    ap.add_argument("--shell", action="append", default=[],
                    help="label substring of a housing; parts intersecting it are wall penetrations")
    ap.add_argument("--max-overlap", type=float, default=1.0,
                    help="mm^3 of shared volume tolerated per pair (default 1.0)")
    ap.add_argument("--ignore", action="append", default=[],
                    help="A:B label substrings whose overlap is by design")
    ap.add_argument("--strict", action="store_true",
                    help="also fail on non-shell interference")
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    asm = _load(a.model).gen_step()
    children = list(getattr(asm, "children", []) or []) or [asm]
    named = [(getattr(c, "label", f"child{i}"), c) for i, c in enumerate(children)]
    print(f"occurrences: {len(named)}")

    hard_fail = False

    # 1) loose parts ---------------------------------------------------------
    loose = [(lbl, len(c.solids())) for lbl, c in named if len(c.solids()) != 1]
    if loose:
        hard_fail = True
        print(f"\nLOOSE PARTS ({len(loose)}) — boolean did not fuse, or a cut severed the body:")
        for lbl, n in loose:
            print(f"  {lbl:40s} {n} solids")
    else:
        print("loose parts: none (every occurrence is exactly 1 solid)")

    def ignored(x, y):
        for rule in a.ignore:
            if ":" not in rule:
                continue
            p, q = rule.split(":", 1)
            if (p in x and q in y) or (p in y and q in x):
                return True
        return False

    is_shell = lambda lbl: any(s in lbl for s in a.shell)   # noqa: E731

    # 2+3) pairwise sharing, with a sound bbox prefilter ----------------------
    pen, other = [], []
    for (la, ca), (lb, cb) in itertools.combinations(named, 2):
        if ignored(la, lb):
            continue
        if _bbox_overlap_volume(ca, cb) <= a.max_overlap:
            continue                                   # cannot exceed tolerance
        v = _shared_volume(ca, cb)
        if v <= a.max_overlap:
            continue
        shells = is_shell(la) + is_shell(lb)
        (pen if shells == 1 else other).append((v, la, lb))
    pen.sort(reverse=True)
    other.sort(reverse=True)

    if a.shell:
        if pen:
            hard_fail = True
            print(f"\nWALL PENETRATION ({len(pen)}) — part embedded in a housing "
                  f"(missing bore, or the case is too small/short):")
            for v, la, lb in pen[:a.top]:
                print(f"  {v:12.2f} mm^3   {la}  <->  {lb}")
            if len(pen) > a.top:
                print(f"  ... {len(pen) - a.top} more")
        else:
            print(f"wall penetration: none (shells: {', '.join(a.shell)})")

    if other:
        print(f"\nINTERFERENCE ({len(other)} pairs over {a.max_overlap} mm^3) — "
              f"review; some is by design, clashing gear teeth are not:")
        for v, la, lb in other[:a.top]:
            print(f"  {v:12.2f} mm^3   {la}  <->  {lb}")
        if len(other) > a.top:
            print(f"  ... {len(other) - a.top} more")
        if a.strict:
            hard_fail = True
    else:
        print(f"interference: none over {a.max_overlap} mm^3")

    bb = asm.bounding_box()
    print(f"\nbbox: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")
    print("RESULT:", "FAIL" if hard_fail else "PASS")
    sys.exit(1 if hard_fail else 0)


if __name__ == "__main__":
    main()
