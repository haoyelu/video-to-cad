#!/usr/bin/env python3
"""Objective silhouette-alignment reward for the closed-loop refinement.

Compares the foreground silhouette of a REFERENCE frame (a view traced from the
video) against a RENDER of the current model from the matched camera, and prints
an IoU score in [0,1]. Use it as a quantitative reward alongside the model's own
visual judgement — NOT as the only signal (it is a heuristic: it ignores internal
features, colour, and fine detail, and it is sensitive to how cleanly the
foreground separates from the background).

Usage:
  silhouette_score.py REFERENCE.png RENDER.png [--ref-bbox x0,y0,x1,y1]
                                               [--bg-tol 28] [--grid 256]
  --ref-bbox : crop the reference to the model region first (strip UI chrome).
  --bg-tol   : how far a pixel must differ from the detected background to count
               as foreground (0-255 grey units).
Both silhouettes are cropped to their bounding box and rescaled into a common
square (aspect-preserving) before IoU, so absolute position/scale don't matter —
only shape/proportion do.
"""
import sys, argparse, numpy as np
from PIL import Image


def _foreground(img, bg_tol):
    a = np.asarray(img.convert("L"), dtype=np.int16)
    # background = median of the 4 border strips (robust to a uniform canvas)
    b = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = int(np.median(b))
    return np.abs(a - bg) > bg_tol


def _norm(mask, grid):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return np.zeros((grid, grid), bool)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    im = Image.fromarray((crop * 255).astype(np.uint8))
    # aspect-preserving fit into grid x grid (letterbox)
    h, w = crop.shape
    s = (grid - 2) / max(h, w)
    im = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.NEAREST)
    out = Image.new("L", (grid, grid), 0)
    out.paste(im, ((grid - im.width) // 2, (grid - im.height) // 2))
    return np.asarray(out) > 127


def score(ref_path, render_path, ref_bbox=None, bg_tol=28, grid=256):
    ref = Image.open(ref_path)
    if ref_bbox:
        ref = ref.crop(ref_bbox)
    rnd = Image.open(render_path)
    m1 = _norm(_foreground(ref, bg_tol), grid)
    m2 = _norm(_foreground(rnd, bg_tol), grid)
    inter = np.logical_and(m1, m2).sum()
    union = np.logical_or(m1, m2).sum()
    return float(inter) / float(union) if union else 0.0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("reference"); ap.add_argument("render")
    ap.add_argument("--ref-bbox"); ap.add_argument("--bg-tol", type=int, default=28)
    ap.add_argument("--grid", type=int, default=256)
    a = ap.parse_args()
    bbox = tuple(int(v) for v in a.ref_bbox.split(",")) if a.ref_bbox else None
    s = score(a.reference, a.render, bbox, a.bg_tol, a.grid)
    print(f"silhouette_iou={s:.3f}")
    # convention for the loop: >=0.85 aligned, 0.70-0.85 close, <0.70 revise
