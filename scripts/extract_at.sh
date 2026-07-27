#!/usr/bin/env bash
# Extract frames at EXACT timestamps, named by their timestamp.
#
# Why this exists: `extract_frames.sh` uses ffmpeg's `fps=1/N` filter, which
# assumes a constant frame rate. On a variable-frame-rate source (most screen
# recordings, and most long YouTube uploads) the filter's output drifts from
# real time — on a 2.5 h capture the drift exceeded a full sampling interval,
# which silently makes EVERY logged timestamp wrong.
#
# `-ss <t>` seeks by real presentation timestamp and does not drift. Use this
# script for any frame whose timestamp you intend to write into the build log.
#
# Usage:
#   extract_at.sh <video> <out_dir> <start_s> <step_s> <end_s> [scale_w]
#   extract_at.sh <video> <out_dir> --list 70 150 2400 4200   [scale_w via SCALE_W env]
#
# Output: t_<seconds>.jpg  (e.g. t_00070.jpg == exactly t=70 s).
#
# Verify before trusting a long run: extract the same timestamp with both this
# script and extract_frames.sh. If the two images differ, the fps filter has
# drifted and only this script's timestamps are usable.
set -euo pipefail

video="${1:?usage: extract_at.sh <video> <out_dir> <start> <step> <end> [scale_w]}"
out="${2:?need output dir}"
mkdir -p "$out"

if [ "${3:-}" = "--list" ]; then
  shift 3
  times=("$@")
  width="${SCALE_W:-0}"
else
  start="${3:?need start seconds}"; step="${4:?need step seconds}"; end="${5:?need end seconds}"
  width="${6:-0}"
  times=()
  t="$start"
  while [ "$t" -le "$end" ]; do times+=("$t"); t=$((t + step)); done
fi

vf=""
[ "${width:-0}" != "0" ] && vf="-vf scale=${width}:-1"

for t in "${times[@]}"; do
  # -ss BEFORE -i keeps the seek fast; ffmpeg still lands on the exact frame.
  # shellcheck disable=SC2086
  ffmpeg -v error -ss "$t" -i "$video" -frames:v 1 $vf -q:v 2 \
         "$out/t_$(printf '%05d' "$t").jpg" -y
done

echo "extracted ${#times[@]} exact-seek frames to ${out}/"
echo "each t_SSSSS.jpg is at exactly SSSSS seconds -> MM:SS (no drift)"
