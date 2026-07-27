# video-to-cad

A Claude Code **skill** that reconstructs a CAD model's build process from a
video (YouTube link or local file) and turns it into runnable parametric CAD,
a timestamp-aligned build log, an engineering per-feature record, and
visual/interactive outputs (exploded views, build+assemble animations, and a
manifest-driven 3D web viewer).

This repo contains the skill **source and docs only** — no videos, CAD files, or
generated artifacts (see `.gitignore`).

## Install
Copy this directory into your Claude Code skills folder:

```bash
cp -r . ~/.claude/skills/video-to-cad
```

It composes with the `cad` and `cad-viewer` skills for geometry generation and
review.

## What it does
- **Reconstruct** (Mode A single part / Mode B recursive segment→build→compose):
  segment the video into components, transcribe exact features + dimensions,
  write build123d `gen_step()` generators, compose an assembly, and refine
  against the video with a reward loop.
- **Record** the exact per-feature build (parametric, traceable) — one checkpoint
  per CAD feature with driving dimensions.
- **Visualize** deterministically from the reconstruction: exploded views, a
  feature-by-feature build + assemble GIF, and an interactive Three.js viewer
  (Assembly / Build components / Run) driven by a `viewer.json` manifest.

## Layout
```
SKILL.md                     # entry point / workflow
scripts/
  extract_frames.sh          # fixed-interval frame extraction
  extract_keyframes.sh       # scene-change keyframes
  clip_frames.py             # per-segment / recursive-tree clip slicing (Mode B)
  silhouette_score.py        # objective refinement reward (silhouette IoU)
  build_recorder.py          # parametric per-feature recorder (STEP + GLB + JSON)
  export_viz.py              # trajectory -> GLBs + viewer.json + build/asm stages
  make_animation.py          # viewer.json -> exploded.png + build_assemble.gif
templates/
  viewer.html                # manifest-driven interactive 3D viewer
references/
  end-to-end.md              # video link -> interactive HTML (full procedure)
  model-routing.md           # cheap-vs-frontier model per pipeline stage
  orchestration.md           # Mode B: recursive segment -> build -> compose
  refine-loop.md             # RL-style closed-loop refinement
  visualization.md           # trajectory -> animations + viewer
  cad-patterns.md            # build123d patterns + gotchas
  operation-map.md           # CAD operation -> build123d mapping
  assembly-patterns.md       # AssemblyHelper mates / reconciliation
  frame-reader-prompt.md     # reusable frame-reader subagent prompt
  build-log-template.md      # timestamped build-log format
```

## The one boundary worth knowing
The **LLM** is needed only to turn the video into a faithful parametric model
(segment, read dimensions, choose operations, write generators, mate, refine).
Everything downstream of that model — records, GLBs, snapshots, exploded views,
animations, and the interactive viewer — is deterministic scripts. See
`references/end-to-end.md`.
