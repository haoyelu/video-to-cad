# Visualization & interactive output (from a reconstruction trajectory)

Once a reconstruction exists — the parametric part generators (`gen_step()`, local
frame), the assembly placement/kinematics, and optionally per-feature build
checkpoints — the visual artifacts are **deterministic and scriptable**. These
skill scripts turn that "trajectory" into: exploded views, a feature-by-feature
build + assemble GIF, and an interactive 3D viewer. No per-asset bespoke code.

```
trajectory ─(viz_spec.py)→ export_viz.py ─→ GLBs + build steps + asm stages + viewer.json
                                              ├─ make_animation.py  → exploded.png + build_assemble.gif
                                              └─ templates/viewer.html + viewer.json → interactive page
```

## 1. Write a thin `viz_spec.py` (the only per-asset input)
Reuse your part modules + assembly kinematics. Attributes (see the worked example
`skill_test/modeB/web/viz_spec.py`):
- `PARTS` = `{id: gen_step_callable}` — distinct meshes, local frame (required).
- `INSTANCES` = `[{part,label,pos,rot_deg,color}]` — assembly placement (required).
- `STAGES` = `[[label,...], ...]` — optional assemble-one-by-one grouping (default: one instance per stage).
- `BUILD` = `{id: [(feature, operation, params, solid), ...]}` — optional per-feature build (drive it with each part's own feature functions; `BuildRecorder` records STEP+GLB).
- `MOTION` = a declarative motion model for the viewer "Run" (optional; see below).
- `TITLE`, `UNITS` — optional.

## 2. Export the assets
```
python <skill>/scripts/export_viz.py path/to/viz_spec.py --out path/to/web
```
Writes `parts/*.glb`, `build_steps/*.{glb,step}` (+ `*.record.json`),
`asm/asm_*.step`, and `viewer.json`.

## 3a. Animations (headless)
```
python <skill>/scripts/make_animation.py path/to/web           # exploded.png + build_assemble.gif
```
Two acts: each component built feature-by-feature (grid), then cumulative
assembly by `assembly_stages`. Renders the recorded STEP stages via the `cad`
snapshot tool and composites with PIL + ffmpeg. Flags: `--camera 35:25 --fps 7 --width 1000`.

Exploded still only, ad hoc, for any labeled STEP:
```
python <cad>/scripts/snapshot --input asm.step --output exploded.png --camera iso \
  --display '{"mode":"rendered","exploded":{"enabled":true,"axis":"z","spacing":1.6}}'
```

## 3b. Interactive viewer
Copy the template next to the manifest and serve the folder:
```
cp <skill>/templates/viewer.html path/to/web/ && cd path/to/web && python3 -m http.server 8099
# open http://127.0.0.1:8099/viewer.html
```
It reads `./viewer.json` and provides three modes — **Assembly** (explode/assemble
scrub, staggered by stages), **Build components** (step through each part's
features with captions/params), **Run** (motion model) — plus orbit/zoom,
auto-rotate, reset. Same for any asset.

## Motion models (viewer "Run")
- `{"type":"crank_slider", axis, throw, rod, pin_bore_z, crank, cylinders:[{x,base_angle_deg,rod,cap,pin,piston,rings}]}` — reciprocating engine.
- `{"type":"spin", part, axis, rpm}` — a single rotating body (shaft, bearing, turbine).
- omit / `null` — Run just auto-rotates.
New mechanism motions (gear train, linkage) = add a case in the viewer + a spec block.

## What's automatic vs. what you must supply
- **Automatic from geometry + records:** exploded views, feature-by-feature build
  stages/GIF, assemble GIF, orbitable viewer with build+assembly modes. Requires
  only that parts are parametric/feature-factored and the assembly is a labeled
  multi-body compound (Mode B output).
- **Needs a supplied model:** realistic **mechanism motion** (the "Run" animation)
  is NOT inferable from shapes — provide a `MOTION` spec for the mechanism type.

## GLB units/orientation note
`export_gltf` writes vertices in **metres**, CAD Z-up, under a node rotated −90°
about X. The viewer template counter-rotates +90° about X and scales ×1000 to the
mm frame (`camera.up=(0,0,1)`), auto-framing from bounding boxes. Snapshot renders
from the STEP files directly (unaffected).
