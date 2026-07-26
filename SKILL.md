---
name: video-to-cad
description: Reconstruct a CAD model's build process from a video (YouTube link or local file) and produce a timestamp-aligned build log plus runnable parametric CAD code. Use when the user gives a CAD/modeling tutorial or screencast (SolidWorks, Fusion 360, Onshape, FreeCAD, Blender-CAD, etc.) and wants the step-by-step modeling process reconstructed, actions recorded against video timestamps, and/or the model rebuilt as CAD (build123d/STEP). Also use for "watch this video and rebuild the part", "extract the modeling steps with timestamps", or "turn this tutorial into CAD code".
---

# Video → CAD build process (with timestamp alignment)

Turn a CAD screencast into two aligned deliverables:
1. **A timestamped build log** — every modeling action mapped to the video time
   at which that state appears on screen (`state → timestamp`).
2. **Runnable parametric CAD code** — a build123d/Python generator that
   reproduces the model feature-by-feature in the SAME order as the video,
   exported to a validated STEP file.

This skill is the recipe. It composes with the `cad` and `cad-viewer` skills
for the actual geometry generation and review.

**Full pipeline (video link → interactive HTML):** see `references/end-to-end.md`
for the end-to-end procedure and commands (download → reconstruct → `export_viz`
→ `make_animation` / `viewer.html`), with the LLM-vs-deterministic breakdown.

## Choose a mode first
- **Mode A — single part / simple model:** run the workflow below end-to-end.
- **Mode B — assembly or long multi-component tutorial (RECURSIVE
  divide-and-conquer):** run ONE self-similar procedure, `reconstruct(node)`,
  starting on the whole video, and let it recurse. At each node the agent decides:
  - **elementary part** → build it directly (Mode A on that clip), OR
  - **composite** (several parts / a sub-assembly / a very complex part) →
    **segment** its clip into children, **spawn one `reconstruct()` subagent per
    distinct child** (siblings in parallel; a repeated child is built once and
    instanced), then **compose** the children by their mate datums into a labeled
    (sub-)assembly.
  This bottoms out at elementary parts, so it terminates; depth adapts to
  complexity (typically assembly ▸ sub-assembly ▸ part). Smaller, focused
  sub-tasks reconstruct better and run in parallel. The agent MUST build this way
  for assemblies — do not attempt one monolithic pass. Full recursive procedure +
  the self-referential subagent prompt + tree-manifest schema:
  `references/orchestration.md`; clip slicing (handles nested trees):
  `scripts/clip_frames.py`.

## When to use
- User supplies a CAD/modeling tutorial video (YouTube URL or local `.mp4`/`.mov`)
  and wants the build process, the timestamps, and/or the model as code.
- Any "watch and reconstruct", "extract steps with timestamps", or
  "rebuild this part from the video" request.

## Required tools
- `ffmpeg` / `ffprobe` (frame extraction, metadata).
- `yt-dlp` (only if the input is a URL — download first).
- Scripts: `extract_frames.sh` (fixed interval), `extract_keyframes.sh`
  (scene-change), `clip_frames.py` (per-segment clips for Mode B),
  `silhouette_score.py` (refinement reward), `build_recorder.py` (parametric
  per-feature record), `export_viz.py` + `make_animation.py` + `templates/viewer.html`
  (visualization pipeline — see `references/visualization.md`).
- The `cad` skill (build123d + `scripts/step`, `scripts/inspect`, `scripts/snapshot`)
  and `cad-viewer` skill for generation, validation, and review links.
- The Read tool renders frames as images — this is how you "watch" the video.
- **Interpreter + path:** run the `cad` launchers with a Python that has
  `build123d` installed (often the anaconda/base env, not a bare `python`), and
  set `PYTHONPATH=<cad-skill>/scripts/packages/cadpy/src` so the launcher can
  import `cadpy`. Both are required; PYTHONPATH alone is not enough if the chosen
  interpreter lacks build123d. `scripts/snapshot` also writes a hidden
  `<part>.step.glb` sidecar — leave it or clean it up, it is not a deliverable.

## Workflow

### 1. Acquire the video
- Local file: use it directly.
- URL (YouTube/other): download with `yt-dlp`, capping resolution to keep it
  small, e.g. `yt-dlp -f "bestvideo[height<=1080]+bestaudio/best" -o video.mp4 <URL>`.
  If `yt-dlp` is missing, tell the user and ask them to download the file, or run
  the `! <command>` form so they can authenticate if needed.
- Read metadata: `ffprobe -v error -show_entries format=duration -show_entries stream=width,height,r_frame_rate <file>`.

### 2. Two-pass frame extraction
Use `scripts/extract_frames.sh` (wraps ffmpeg). Extract to a scratch folder you
delete at the end.
- **Overview pass** — one frame every ~30 s to learn the tool, the overall
  feature order, and where the real build starts (tutorials often open with a
  finished-model preview montage; the real build usually starts when a blank
  sketch/part appears).
- **Detail pass** — one frame every ~10 s (or 5 s around dimension-heavy sketch
  moments) once you know the structure. Frame `N` is at `t = (N-1) * interval`
  seconds; convert to MM:SS.
- **Scene-change pass (essential for time-lapses)** — fixed-interval sampling
  misses feature commits that happen between samples. Use
  `scripts/extract_keyframes.sh <video> <dir> [threshold]` to grab the frames
  where the picture actually changes (feature committed, view rotated, dialog
  opened). Output frames are timestamp-named `k_SSSSS.jpg`. In a fast time-lapse
  this recovers far more of the real operation sequence than any fixed interval.

### 2b. Find and trace the orthographic views (decisive for fidelity)
Before coding, hunt for the frames where the tool shows clean **orthographic
views** — a side elevation, a top/plan, a bow/stern-on. Tutorials almost always
present these near the end (final render / appearance stage) and often mid-build.
Extract those specific frames at full resolution and **trace real proportions
from them** (sheer line, bow rake, keel, transom, superstructure tier
lengths/heights, mast height, deck/plan outline). Guessing proportions from
scattered perspective frames is the #1 cause of a reconstruction that is "not
even close"; tracing the shown ortho views is what closes the gap. For hulls and
other doubly-curved bodies, build by **two-view intersection** (see
`references/cad-patterns.md`): the traced side silhouette extruded across the
beam, intersected with the traced plan outline extruded vertically.

### 3. Read the frames (transcribe, don't summarize)
Read frames in batches with the Read tool. For each meaningful state capture:
- **Video timestamp** (MM:SS).
- **Active feature/tool** — from the title bar (e.g. "SketchN of Part4"), the
  PropertyManager/panel heading, and the ribbon button.
- **EVERY numeric dimension on screen** — exact values (`250.00`, `R75.00`,
  `⌀300`, `45.00deg`, offsets). These are the load-bearing output; do not round
  or paraphrase them.
- **Sketch plane / reference** and how each datum plane was defined
  (reference, angle, offset).
- **Construction method** — spline vs arc vs line; circle+tangent-lines airfoil;
  loft vs revolve vs extrude vs sweep; relations (Tangent/Symmetric/Equal);
  guide curves; patterns; wraps; mirrors; fillets.
- **Sub-features a coarse pass misses** — rounded trailing edges, double arcs,
  pylons, guide-curve sweeps, exact window size/count/pitch, fillet targets,
  final appearance color, part rename.

**Read the FeatureManager / history tree, not just the viewport.** The tree
panel (left side in SolidWorks/Fusion/Onshape) lists every feature by name in
build order — `Revolve1`, `Loft3`, `Mirror2`, `LPattern1`, `Wrap1`, `Fillet6`,
`Plane8`, etc. In a time-lapse the *action* often happens off-camera, but the
tree text still tells you the exact operation, its type, and its order. Zoom into
frames where the tree is legible (often the final frames) and transcribe the full
tree — it is the authoritative operation list even when you never saw the click.
Feature names also disambiguate operations the viewport is ambiguous about
(Boss-Extrude vs Loft vs Sweep).

**Parallelize for long videos.** Split the frame range across several
`general-purpose` subagents (≈35 frames each), each returning a chronological
`timestamp — feature — [exact dims] — notes` list plus a "DETAILS POSSIBLY
MISSED" section. Then synthesize. See `references/frame-reader-prompt.md` for the
exact subagent prompt to reuse.

### 4. Write the timestamped build log
Produce a markdown file (`<part>_build_process.md`) using
`references/build-log-template.md`. One row per action:
`time — action — exact dimensions — (later) the code function that reproduces it`.
Group by feature in build order. State the sampling resolution and the ±tolerance.
Record the final on-screen **feature-tree order** verbatim — it is the spec for
the code's operation order.

### 5. Generate the CAD code (invoke the `cad` skill)
Write a build123d generator (`<part>.py` with `def gen_step(): ...`) that mirrors
the feature tree.

**Scale the ambition to the model's complexity (do this triage first).**
Many tutorials build far more than a single tractable part (dozens of bodies,
hundreds of features, multi-file "episodes", time-lapse editing). "One function
per feature" and "every action timestamped" only hold for tractable parts. Pick a
tier and state which you used:
- **Full** (≤ ~30 features, one/few bodies): reproduce every feature 1:1.
- **Primary-form** (many bodies / hundreds of features / time-lapse): faithfully
  reconstruct the **primary form-defining masses in tree order** (hull, decks,
  superstructure, mast, etc.), reproduce every **legible** dimension exactly, and
  **log the remaining detail features as caveats** rather than modeling them.
  This is expected, not a failure — say so in the deliverables.

**Assemblies (multi-part mechanical models).** If the tutorial builds several
parts and mates them (engine, gearbox, robot, enclosure + hardware), reconstruct
it as a **labeled assembly**, not one fused solid. Decompose from the tutorial's
own part files / Assem1 tree (it names every component), write one `make_*()` per
part with its origin on its mating datum, then assemble with
`cadpy.assembly.AssemblyHelper` (fixed-root first, named frames + `connect`/
`coaxial`/`face_to_face`, `revolute_frame`/`linear_frame` for motion, per-instance
labels for repeated parts, `add_module` for functional sub-assemblies). Return the
labeled Compound from `asm.build()`. Full recipes + validation in
`references/assembly-patterns.md`. Keep it a labeled Compound (don't fuse) so each
part stays selectable and independently refinable.

**`gen_step()` return-type contract** (the `cad` launcher enforces this):
- Return a single fused **Solid/Part**, OR a **labeled Compound** of solids
  (set `.label` on the compound and on each child). A bare/loose Compound with
  unlabeled children is read as a malformed *assembly* and rejected.
- `a + b` fuses **only if the shapes overlap**; on disjoint parts it yields a
  loose ShapeList, not a fused solid. Embed roots a few mm into the parent (or
  add an overlapping strut) so booleans fuse. Verify with
  `inspect refs --facts` → `shapeCount: 1` (or the intended labeled-compound count).

Guidance:
- **One function per feature**, named and commented with its video timestamp and
  exact dimensions, so the code and the log cross-reference.
- **Match the construction to the video**: revolve for bodies of revolution;
  loft between real section sketches for wings/blades/nacelles; mirror for
  symmetry; pattern + cut for repeated features; fillet last. Translate each
  tree feature to its build123d equivalent via `references/operation-map.md` so
  a Sweep isn't rebuilt as a Loft, etc.
- **Reproduce section shapes faithfully** — e.g. a two-radius teardrop airfoil
  (rounded LE *and* TE joined by external tangent lines), not a sharp
  approximation. See `references/cad-patterns.md` for reusable build123d
  helpers (airfoil, nacelle loft, planes, window pockets).
- Put every legible dimension in a **named parameter**.
- Where the video derives geometry from angled reference planes whose exact math
  is ambiguous on screen, reconstruct placement to look correct but keep the
  **exact cross-section dimensions**; say so explicitly in a caveat.
- Note toolkit gaps honestly (e.g. build123d has no `Wrap`; emulate engraved
  features as shallow patterned pocket cuts).

### 6. Validate, snapshot, review
- Generate: `python <cad-skill>/scripts/step <part>.py` (set
  `PYTHONPATH=<cad-skill>/scripts/packages/cadpy/src` if the launcher can't
  import `cadpy`).
- Inspect: `python <cad-skill>/scripts/inspect refs <part>.step --facts` —
  confirm it is a single solid (or an intended labeled compound) with sane bounds.
- Snapshot iso/top/side/front with `scripts/snapshot` and **Read the PNGs** to
  compare against the video's final model. Fix the largest visual discrepancy
  (wrong feature position, missing sub-feature, no fusion) and regenerate.
- **Camera-matched overlay loop (the fidelity-closing step).** For each traced
  orthographic frame (step 2b), render the model from the *same* view and put the
  two side by side:
  - side elevation → `--camera iso` reads best, or an explicit `"90:12"` angle;
    top → `--camera top`; bow/stern-on → `--camera front`.
  - Compare silhouette, proportion, and feature placement against the traced
    frame. List concrete mismatches (bow too blunt, superstructure too far aft,
    mast too short) and fix the responsible parameter — you already traced the
    right numbers, so this is dialing, not guessing.
  - Repeat until the silhouettes overlay. Do NOT stop at "recognizable"; that is
    the trap that produced "not even close". Iterate to matching proportions.
  - **This is a reward-driven loop — run it that way (see `references/refine-loop.md`).**
    Score each render objectively with
    `python scripts/silhouette_score.py REF.png RENDER.png [--ref-bbox …]`
    (→ `silhouette_iou`; ≥0.85 aligned) AND with the fidelity rubric, change the
    ONE parameter that fixes the worst mismatch, regenerate, and repeat until the
    reward stops rising or you hit the threshold. Refine bottom-up: each **part**
    against its own reference first, then the **assembly**, then the whole model.
    For multi-part models, fan out one refiner subagent per part (each runs its
    own loop and returns converged parameters), then refine the assembly.
  - Snapshot camera presets map to the model's bounding box, so `left/right` may
    render end-on for a long part; use `iso` plus an explicit `azimuth:elevation`
    for a true broadside.
  - **Long-axis parts / enclosing shells — snapshot limits (known):** the
    snapshot tool normalizes to the bbox (orients the longest axis vertically) and
    renders color-alpha as OPAQUE, so a true horizontal broadside or a
    see-through outer shell isn't possible in a static shot. Workarounds: snapshot
    the CORE with the enclosing shell hidden (or a temporarily shortened shell),
    use explicit `azimuth:elevation`, and hand the STEP to `cad-viewer` (the
    viewer rotates freely and can hide/isolate occurrences — the right tool for
    reviewing long or nested assemblies).
- Hand the STEP path to `cad-viewer` and return the live link.

### 7. Iterate on fidelity
The first pass gets the feature sequence; a second dense pass gets exact
dimensions and missed sub-features. When the user says "details missed",
re-extract denser frames, re-read (parallel subagents), and refine both the log
and the code. Confirm which numbers are exact vs. reconstructed.

**Fidelity self-critique (score before you hand off).** After the overlay loop,
grade the model against the traced ortho frames and only ship when it clears the
bar — don't wait to be told "not even close":
1. **Silhouette** — does the side profile overlay the traced elevation (bow rake,
   sheer, keel, transom / nose, tail)? 
2. **Proportion** — overall L×W×H ratios and the fore/aft position of the main
   masses within ±10%?
3. **Feature completeness** — is every feature in the transcribed tree either
   modeled or explicitly logged as an omitted detail?
4. **Construction match** — was each feature built with the operation the tree
   named (per `operation-map.md`), not a lookalike?
5. **Dimensions** — is every *legible* on-screen number a named parameter with
   the exact value?
6. **Appearance** — colors / two-tone split / part name applied?
Name the weakest axis and fix it before delivering; report the remaining gap
honestly rather than overselling "recognizable" as "faithful".

## Troubleshooting
- **`BRep_API: command not done` / zero-length edge** — duplicate consecutive
  sketch points (common when mirroring a half-outline through the centreline).
  Drop the repeated centreline points.
- **`Unknown Compound type, color not set`** — you set `.color` on a loose
  Compound. Return a single solid, or a labeled Compound and set `.color`/`.label`
  on each child solid.
- **`shapeCount` > intended** — parts didn't fuse because they don't overlap.
  Embed roots a few mm into the parent or add an overlapping strut; `a + b` only
  fuses touching solids.
- **Launcher `ModuleNotFoundError: cadpy`** — set
  `PYTHONPATH=<cad-skill>/scripts/packages/cadpy/src`; and use an interpreter that
  has `build123d` (often anaconda base), not a bare `python`.
- **Snapshot `left/right` looks end-on** — presets map to the bounding box; use
  `iso` plus an explicit `azimuth:elevation` (e.g. `"90:12"`) for a broadside.
- **Fillet fails** — radius exceeds local geometry; shrink it, keep fillets last,
  and wrap in `try/except` so one bad edge doesn't abort the whole model.

## Worked examples (in this environment)
- **MD-11 airliner** — revolve fuselage + lofted wings/stabs/fin + tail engine +
  wrapped windows; two-radius airfoil sections; single fused solid.
- **Naval corvette** — trace-based two-view hull, tumblehome tiered
  superstructure, mast with platform+yardarm, waterline two-tone; the trace-based
  redo (`corvette_v2`) is the reference for closing the fidelity gap on a
  complex, undimensioned time-lapse.
- **Four-cylinder engine (assembly)** — part decomposition (crankshaft, piston,
  conrod, wrist pin), mate-driven `AssemblyHelper` placement with named frames +
  `connect`, 4 cylinders as repeated instances at crank angles [0,180,180,0], a
  revolute datum on the crank axis → a labeled 13-occurrence assembly. See
  `references/assembly-patterns.md`.

## The refinement mindset (RL-style)
Reconstruction quality comes from iterating against a reward, not one pass. The
model is the policy (it edits parameters), the video frame is the reference, and
the reward = `silhouette_score.py` IoU + the fidelity rubric. Take the edit that
raises the reward; repeat per component, bottom-up, until aligned. When a miss is
*systematic*, fix the **skill** (patterns/scripts/rules), not just the model —
the skill is the durable policy that should get better every run. Full algorithm:
`references/refine-loop.md`.

### 8. Visualization (optional, fully scriptable)
Once the model exists, the visual artifacts are deterministic — no bespoke code.
Write a thin `viz_spec.py` (part generators + assembly placement + optional
per-feature `BUILD` + optional `MOTION`), then:
`export_viz.py viz_spec.py --out web` → GLBs + build steps + `viewer.json`;
`make_animation.py web` → exploded.png + build+assemble GIF;
`cp templates/viewer.html web/ && serve` → interactive 3-mode viewer
(Assembly / Build components / Run). Full guide + schemas + the exact-vs-supplied
line (mechanism motion needs a MOTION spec): `references/visualization.md`.

## Deliverables (report all in the final message)
- `<part>_build_process.md` — timestamp-aligned build log.
- `<part>.py` — build123d generator (one function per feature, timestamped).
- `<part>.step` — validated STEP solid.
- Verification snapshots + the `cad-viewer` link.
- A short caveats list: sampling tolerance, exact-vs-reconstructed dimensions,
  toolkit substitutions.

## Non-negotiables
- Timestamps map to the **state visible on screen**, at the stated sampling
  resolution (±half the interval); say so — do not imply frame-exact timing
  unless you verified it.
- Transcribe **exact** on-screen dimensions; never invent or round silently.
- The code's operation order must match the video's **feature-tree order**.
- Delete scratch frame folders when done; keep only the deliverables.
- Report only checks that actually ran.
