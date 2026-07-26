#!/usr/bin/env python3
"""Extract per-segment frame folders from a segmentation manifest.

Phase-1 of segmented reconstruction produces a manifest marking each component's
clip [start,end]. This tool slices the video into one frame folder per segment so
each builder reads only its own clip. Supports BOTH a flat manifest and a
RECURSIVE (tree) manifest for hierarchical decomposition.

Flat schema:
{
  "video": "engine.mp4", "units": "mm",
  "interfaces": {"pitch_radius": 21.14, "roller_dia": 7.0, "n_rollers": 12},
  "segments": [ {"id":"crankshaft","kind":"part","start":"0:40","end":"6:10","notes":"..."} ],
  "assembly": {"start":"38:00","end":"42:40","notes":"..."}
}
# "interfaces" (optional): shared MATING dims all relevant parts must build to,
# so independently-built parts actually fit. Pass them to every builder; the
# composer reconciles any conflicts. See orchestration.md.

Recursive (tree) schema — a node either is a LEAF part (no children) or an
internal node that decomposes into children and composes them:
{
  "video": "engine.mp4",
  "root": {
    "id":"engine","kind":"assembly","start":"0:00","end":"42:40",
    "compose":{"notes":"crank=root; 4 cylinder modules on pins"},
    "children":[
      {"id":"crankshaft","kind":"part","start":"8:00","end":"18:00","notes":"..."},
      {"id":"cylinder_module","kind":"assembly","repeat":4,"start":"0:00","end":"8:00",
       "compose":{"notes":"piston+rings+pin+rod+cap"},
       "children":[ {"id":"piston","kind":"part","start":"0:00","end":"6:30"}, ... ]}
    ]
  }
}

Usage:
  clip_frames.py manifest.json [--interval 8] [--width 1280] [--outdir clips]
  # "video" in the manifest resolves RELATIVE TO THE MANIFEST FILE'S directory
  # (or pass an absolute path). If the manifest lives in a subfolder and the video
  # is elsewhere, use an absolute path to avoid confusion.

Output: nested folders mirroring the tree. Leaf nodes -> <outdir>/<path>/k_<sec>.jpg;
internal nodes also get <outdir>/<path>/_compose/ (their composition reference).
Frames are named by ABSOLUTE video seconds so timestamps stay meaningful.
"""
import argparse, json, os, subprocess, sys


def to_sec(v):
    if isinstance(v, (int, float)):
        return float(v)
    parts = [float(p) for p in str(v).split(":")]
    s = 0.0
    for p in parts:
        s = s * 60 + p
    return s


def extract(video, start, end, interval, width, outdir):
    os.makedirs(outdir, exist_ok=True)
    # temp sequential frames, then rename to absolute-second names
    tmp = os.path.join(outdir, "_seq_%05d.jpg")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(start), "-to", str(end), "-i", video,
         "-vf", f"fps=1/{interval},scale={width}:-1", tmp],
        check=False,
    )
    seq = sorted(f for f in os.listdir(outdir) if f.startswith("_seq_"))
    for i, f in enumerate(seq):
        sec = int(round(start + i * interval))
        os.replace(os.path.join(outdir, f), os.path.join(outdir, f"k_{sec:05d}.jpg"))
    return len(seq)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--interval", type=float, default=8.0)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--outdir", default="clips")
    a = ap.parse_args()

    man = json.load(open(a.manifest))
    base = os.path.dirname(os.path.abspath(a.manifest))
    video = man["video"]
    if not os.path.isabs(video):
        video = os.path.join(base, video)
    if not os.path.exists(video):
        sys.exit(f"video not found: {video}")

    count = [0]

    def do(node, parent):
        path = os.path.join(parent, node["id"])
        children = node.get("children")
        s, e = to_sec(node["start"]), to_sec(node["end"])
        rpt = "  (×%d)" % node["repeat"] if node.get("repeat") else ""
        if children:                                    # internal node: compose ref + recurse
            out = os.path.join(path, "_compose")
            n = extract(video, s, e, a.interval, a.width, out)
            print(f"{path+'/_compose':40s} {s:7.0f}-{e:<7.0f}s -> {n:3d} frames{rpt}")
            count[0] += 1
            for c in children:
                do(c, path)
        else:                                           # leaf part: build frames
            n = extract(video, s, e, a.interval, a.width, path)
            print(f"{path:40s} {s:7.0f}-{e:<7.0f}s -> {n:3d} frames{rpt}")
            count[0] += 1

    if "root" in man:                                   # recursive tree manifest
        do(man["root"], a.outdir)
    else:                                               # flat manifest
        for seg in man.get("segments", []):
            do(seg, a.outdir)
        if man.get("assembly"):
            do({**man["assembly"], "id": "_assembly"}, a.outdir)
    print(f"\ndone: {count[0]} nodes -> {a.outdir}/")


if __name__ == "__main__":
    main()
