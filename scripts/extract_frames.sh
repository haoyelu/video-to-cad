#!/usr/bin/env bash
# Extract evenly-spaced frames from a video for reading with the Read tool.
#
# Usage:
#   extract_frames.sh <video> <interval_seconds> <out_dir> [scale_width]
#
# Frame files are named f_0001.jpg, f_0002.jpg, ...  Frame N is at
# video time t = (N-1) * interval seconds.  Convert to MM:SS when logging.
#
# Examples:
#   extract_frames.sh tutorial.mp4 30 frames_overview 960   # coarse overview
#   extract_frames.sh tutorial.mp4 10 frames_detail  1280   # dense detail pass
set -euo pipefail

video="${1:?usage: extract_frames.sh <video> <interval_s> <out_dir> [scale_w]}"
interval="${2:?need interval in seconds}"
out="${3:?need output dir}"
width="${4:-1280}"

mkdir -p "$out"
# fps=1/interval  ->  one frame every <interval> seconds, first frame at t=0.
ffmpeg -v error -i "$video" \
  -vf "fps=1/${interval},scale=${width}:-1" \
  "$out/f_%04d.jpg"

count=$(find "$out" -maxdepth 1 -name 'f_*.jpg' | wc -l | tr -d ' ')
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$video" 2>/dev/null || echo "?")
echo "extracted ${count} frames to ${out}/ (interval=${interval}s, video≈${dur}s)"
echo "frame N is at t=(N-1)*${interval}s  ->  MM:SS"
