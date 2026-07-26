#!/usr/bin/env bash
# Extract SCENE-CHANGE keyframes from a video — the frames where the picture
# changes materially (a feature committed, the view rotated, a dialog opened).
# For CAD time-lapses this catches feature commits that fixed-interval sampling
# skips between samples. Complements extract_frames.sh (use both).
#
# Usage:
#   extract_keyframes.sh <video> <out_dir> [threshold] [scale_width]
#     threshold: scene-change sensitivity 0.0-1.0 (default 0.15; lower = more
#                frames). Each output frame's timestamp is burned into its name.
#
# Output: k_<seconds>.jpg  (e.g. k_00012.jpg == a keyframe at t=12s).
#
# Example:
#   extract_keyframes.sh tutorial.mp4 frames_key 0.12 1280
set -euo pipefail

video="${1:?usage: extract_keyframes.sh <video> <out_dir> [threshold] [scale_w]}"
out="${2:?need output dir}"
thr="${3:-0.15}"
width="${4:-1280}"

mkdir -p "$out"
# Select scene-change frames. NOTE: the showinfo filter logs at INFO level, so
# we must NOT pass -v error (that would suppress the pts_time we parse below).
ffmpeg -hide_banner -nostats -i "$video" \
  -vf "select='gt(scene,${thr})',scale=${width}:-1,showinfo" \
  -vsync vfr "$out/seq_%05d.jpg" 2> "$out/_showinfo.log" || true

# Rename sequential outputs to their real source timestamps parsed from
# showinfo. Two-pass (via a temp prefix) so a timestamp name can't clobber a
# not-yet-processed sequential file.
python3 - "$out" <<'PY' 2>/dev/null || true
import os, re, sys, glob
d = sys.argv[1]
times = [float(m) for m in
         re.findall(r"pts_time:([0-9.]+)", open(os.path.join(d, "_showinfo.log")).read())] \
        if os.path.exists(os.path.join(d, "_showinfo.log")) else []
files = sorted(glob.glob(os.path.join(d, "seq_*.jpg")))
tmp = []
for i, f in enumerate(files):                       # pass 1 -> unique temp names
    t = os.path.join(d, f"_tmp_{i:05d}.jpg")
    os.replace(f, t); tmp.append(t)
for i, t in enumerate(tmp):                          # pass 2 -> timestamp names
    sec = int(round(times[i])) if i < len(times) else i
    os.replace(t, os.path.join(d, f"k_{sec:05d}.jpg"))
PY

count=$(find "$out" -maxdepth 1 -name 'k_*.jpg' | wc -l | tr -d ' ')
echo "extracted ${count} scene-change keyframes to ${out}/ (threshold=${thr})"
echo "each k_SSSSS.jpg is stamped with its timestamp in seconds -> MM:SS"
