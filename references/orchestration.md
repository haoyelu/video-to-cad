# Segmented (divide-and-conquer) reconstruction

For anything beyond a single tractable part — assemblies, or a long tutorial that
builds several components in sequence — reconstruct it in three phases:
**segment → build each component → compose.** Each phase is a *smaller* task with
a *narrower* focus, which the model does better than one monolithic pass, and the
component builds are independent so they parallelize.

```
video ──▶ [Phase 1: SEGMENT]  one clip per elementary component (+ the compose clip)
              │
              ├─▶ [Phase 2: BUILD]  one builder per clip  → part_i.py / .step   (parallel)
              │                     (each = the normal video-to-cad flow, clip-scoped)
              │
              └─▶ [Phase 3: COMPOSE] mate the finished parts into the assembly
                                     (composition only — parts are frozen)
```

## Phase 1 — Segment (the "major agent")
Watch the whole video coarsely (scene-change keyframes + the part-file/assembly
title bar and FeatureManager tree). Emit a **manifest** marking each elementary
component's clip and the composition clip. One segment = one part the tutorial
builds as its own file/body; the boundary is usually a new part title
("Part3 of …") or a new body in the tree.

Manifest schema (`segments.json`) — consumed by `scripts/clip_frames.py`:
```json
{
  "video": "engine.mp4", "software": "SolidWorks 2020", "units": "mm",
  "segments": [
    {"id":"crankshaft","kind":"part","start":"8:00","end":"18:00","notes":"journals+pins+webs, ⌀48, throw 40"},
    {"id":"connecting_rod","kind":"part","start":"18:00","end":"24:00","notes":"big/small end, length 90"}
  ],
  "assembly": {"start":"30:00","end":"42:40","notes":"crank=root; conrod coaxial on pin; wrist pin coaxial; 4 cyl, throws [0,180,180,0]"}
}
```
Then slice the video into per-component frame folders:
```
python scripts/clip_frames.py segments.json --interval 8 --outdir clips
# -> clips/<id>/k_<sec>.jpg  and  clips/_assembly/  (frames named by absolute video seconds)
```
Segmenter subagent prompt (reuse):
> "Watch this CAD tutorial. Identify each ELEMENTARY component it builds (new
>  part file / new body / new FeatureManager root). For each, give a stable id,
>  kind (part), and the [start,end] MM:SS clip that builds it, plus a one-line
>  notes with its key dimensions. Then give the assembly clip [start,end] and the
>  mates used. Output the segments.json schema above. Use scene-change keyframes
>  and the title bar to place boundaries; timestamps within ~30 s are fine."

## Phase 2 — Build each component (parallel builders)
Fan out one `general-purpose` builder per segment. Each runs the **standard
video-to-cad flow scoped to its clip** (SKILL.md steps 2b–7 + `refine-loop.md`):
read only `clips/<id>/`, trace ortho views, write `parts/<id>.py` with
`gen_step()`, generate + validate + snapshot, and run the closed-loop refinement
against that component's own reference frames until its reward clears threshold.
Builder subagent prompt (reuse):
> "Reconstruct ONLY the `<id>` part from frames in `clips/<id>/` (video seconds
>  in the filenames). Follow the video-to-cad skill: trace its orthographic
>  views, build `parts/<id>.py` (build123d `gen_step()` returning one solid),
>  generate `parts/<id>.step`, snapshot, and run the closed-loop refinement
>  (`refine-loop.md`) against clips/<id>/ until silhouette_iou≥0.85 or no gain.
>  Return the file paths, final reward, key dimensions, and the part's local
>  origin/axis convention (needed for mating)."

Have each builder report its **part-local datum convention** (origin, primary
axis, mating faces) — Phase 3 needs it. Build parts on their mating datums.

## Phase 3 — Compose (composition-only agent)
A single agent (or the main loop) imports the finished parts and assembles them —
**no part re-modeling**, only mates/placement. This narrow focus is why it
performs better. Use `references/assembly-patterns.md`: `AssemblyHelper`,
fixed-root first, named frames + `connect`/`coaxial`/`face_to_face`, repeated
instances for patterned components, labeled Compound. Import each part with
`from build123d import import_step` (or import the builders' `gen_step`), then mate
using the datum conventions the builders reported. Refine at the assembly level
against `clips/_assembly/` with the same reward loop.
Composer subagent prompt (reuse):
> "Compose these finished parts into the assembly using AssemblyHelper. Do NOT
>  re-model any part. Parts + their datum conventions: <list>. Assembly intent
>  from clips/_assembly/: <mates/counts/pattern>. Fixed root = <part>. Return
>  assembly.py, assembly.step, a snapshot, and the assembly-level reward."

## Why this beats one monolithic pass
- Each builder holds only one part's frames/dimensions in context → less to track,
  higher fidelity, and independent parallel work.
- The composer reasons purely about mates/placement, not geometry → fewer degrees
  of freedom, fewer mistakes.
- Failures localize to one component and are cheap to re-run; a bad part doesn't
  corrupt the others.
- It matches the hierarchy in `refine-loop.md`: refine parts, then sub-assemblies,
  then the whole — reward-driven at every level.

## Recursive decomposition (arbitrary depth)
Segment → build → compose is one level of a tree. When a "component" is itself
complex — a sub-assembly, or a single part with many features — **recurse**: treat
its clip as a fresh reconstruction and decompose it further. Leaves are elementary
parts (build directly); internal nodes decompose then compose their children.

Tree manifest (`clip_frames.py` extracts nested clip folders from it):
```json
{ "video":"engine.mp4",
  "root": {"id":"engine","kind":"assembly","start":"0:00","end":"42:40",
    "compose":{"notes":"crank=root; 4 modules on pins [0,180,180,0]"},
    "children":[
      {"id":"crankshaft","kind":"part","start":"8:00","end":"18:00"},
      {"id":"cylinder_module","kind":"assembly","repeat":4,"start":"0:00","end":"8:00",
       "compose":{"notes":"piston+rings+pin+rod+cap"},
       "children":[ {"id":"piston","kind":"part","start":"0:00","end":"6:30"}, … ]}
    ]}}
```
`python scripts/clip_frames.py engine_tree.json` → `clips/engine/crankshaft/`,
`clips/engine/cylinder_module/piston/`, and `_compose/` folders at each internal
node (its composition reference).

**Algorithm (post-order):**
```
build(node):
    if node has no children:                 # LEAF part
        return Phase-2 builder on node's clip -> {gen_step(), datum, dims}
    kids = [ build(c) for c in node.children ]   # RECURSE (parallel per level)
    return Phase-3 composer over kids on node._compose -> {sub-assembly, datum}
```
Return, at every node, a `gen_step()` + a **mate datum** for the node as a whole
(e.g. the cylinder module's datum = the rod big-end bore that seats on a crank
pin). The parent composes purely against children's datums — it never looks
inside them. Compose bottom-up; the root returns the final labeled Compound
(occurrences nest: engine ▸ cylinder_2 ▸ piston).

**Decide when to recurse (the decompose decision at each node):**
- Recurse if the clip builds *multiple* bodies/parts, or one part with many
  features you'd rather isolate. Stop (make it a leaf) once the node is a single
  tractable part reconstructable in one focused pass.
- Don't over-decompose: a plain pin or ring is a leaf, not a sub-tree.

**Repeated sub-assemblies (`repeat`):** build the module ONCE, instantiate N times
at computed placements (the 4 cylinder modules seat on the 4 crank pins). Huge
saving vs rebuilding identical branches.

**Build recursively — the agent applies ONE self-similar procedure to every
node.** Do not hand-write a fixed 2-phase pipeline; instead run `reconstruct(node)`
on the root and let it recurse. Each invocation makes its own leaf-vs-decompose
decision, so the depth adapts to the model:

```
reconstruct(node, clip, expected_datum):     # returns {gen_step_path, datum, dims}
  look at the clip and decide:
  ── LEAF  (one elementary part):
       run the standard single-part flow (SKILL.md steps 2b–7 + refine-loop) on
       `clip`; write parts/<node.id>.py; return its path + mate datum + dims.
  ── COMPOSITE (several parts, a sub-assembly, or one very complex part):
       1. SEGMENT `clip` into child nodes (a sub-manifest) with clip_frames.py.
       2. For each DISTINCT child: RECURSE — spawn a subagent that runs THIS SAME
          reconstruct() procedure on the child. Run siblings in parallel.
          (A child marked repeat:k is reconstructed ONCE, then instantiated k×.)
       3. COMPOSE the children by their returned datums into a labeled
          (sub-)assembly (assembly-patterns.md); refine vs the node's _compose clip.
       4. return compose.py path + THIS node's mate datum (how the parent seats it).
  BASE CASE: always bottom out at leaf parts, so the recursion terminates.
```

The reusable **recursive reconstructor prompt** (spawn on the root; it re-spawns
itself on children) — this is the instruction that makes the build recursive:
> "You are reconstructing node `<id>` (`<kind>`) from clip `<dir>/` (frames named
>  by video seconds). FIRST decide: is this ONE elementary part, or is it
>  COMPOSITE (multiple parts / a sub-assembly / a part with many features)?
>  • If ELEMENTARY: build it per the video-to-cad skill (trace ortho views →
>    `gen_step()` → validate → snapshot → closed-loop refine). Return the .py
>    path, the part's mate datum (origin + primary axis + mating face/bore), and
>    key dims.
>  • If COMPOSITE: segment its clip into children (id, kind, start/end, repeat?),
>    run `clip_frames.py`, then for each distinct child SPAWN ONE SUBAGENT WITH
>    THESE SAME INSTRUCTIONS on that child (siblings in parallel). When they
>    return, COMPOSE them by their datums into a labeled assembly (AssemblyHelper,
>    fixed-root first), refine against the `_compose` clip, and return the
>    compose .py path + THIS node's mate datum. Reconstruct a repeat:k child once
>    and instance it k×.
>  Always bottom out at elementary parts so the recursion terminates. Report your
>  node's output path, its datum, and a one-line fidelity note."

**Depth & cost control (state these when you recurse):** cap recursion depth
(2–3 is plenty for most mechanisms — assembly ▸ sub-assembly ▸ part); make a node
a LEAF as soon as it's a single tractable part; reconstruct repeated branches
once. If nested agent spawning is unavailable in your runtime, execute the SAME
recursion iteratively as a post-order walk (build all leaves, then compose
internal nodes bottom-up) — identical result, one controller.

**Worked example (this repo):** `modeB/cylinder_module.py` composes the 5 leaf
parts into a sub-assembly; `modeB/engine_recursive.py` composes crankshaft + 4
module instances → a nested 34-occurrence assembly (same geometry as the flat
build, now hierarchical). `skill_test/engine_tree.json` is the tree manifest.

## Interface dimensions & reconciliation (critical for parts that must FIT)
Independent builders read dimensions in isolation, so a dimension SHARED across
parts (a raceway two rings + a roller must all agree on, a bolt circle, a bore/pin
fit, a pitch radius) will often come back INCONSISTENT — each builder picks a
plausible value from its own clip and they don't mate. Prevent and repair this:

1. **Declare the interface in Phase 1.** When segmenting, also extract the shared
   MATING dimensions into the manifest and pass them to every relevant builder so
   they build to the SAME numbers. Add an `interfaces` block:
   ```json
   "interfaces": {
     "roller_dia": 7.0, "pitch_radius": 21.14, "n_rollers": 12,
     "inner_raceway_dia": 35.28, "outer_raceway_dia": 49.28
   }
   ```
   Tell each builder: "these interface dims are fixed — build your part to them;
   only free (non-mating) dims are yours to read."
2. **Reconcile in Phase 3 (do NOT assume parts fit).** Before composing, check the
   mating dims the builders reported actually agree (e.g. outer_raceway −
   inner_raceway == roller_dia; pitch_radius == inner_raceway_r + roller_r).
   If they conflict, derive ONE coherent set from the most reliable reading
   (usually the clearest on-screen dimension) and ADJUST the offending part's
   parameter, then regenerate it. Record the reconciliation in the part's header.
   (Real example: the roller-bearing outer ring came back with raceway r=30.5 while
   roller ⌀7 + inner raceway r17.64 + cage pitch 21.14 required r=24.64; the
   composer fixed the outer ring to 24.64.)
3. A quick `inspect measure` between the two mating datums (should be ≈0 gap / the
   intended clearance) catches a bad fit before you ship.

## Phase-2 robustness
- After builders return, VERIFY every part file exists and generates a clean solid
  (`step` + `inspect`); a builder can drop mid-run. Rebuild any missing part —
  and for trivial parts (a pin, a ring, a roller) it's faster and more reliable to
  build them inline than to re-spawn an agent.
- Have builders write their `gen_step()` file EARLY (before refining) so a dropped
  connection still leaves a usable first pass.

## Cautions
- Get part-local **datum conventions** agreed up front (origin on the mate
  face/axis), or Phase 3 becomes awkward transforms.
- Each node must expose ONE datum for its parent; if a sub-assembly's mate to its
  parent is ambiguous, define it explicitly (e.g. module origin = rod big-end bore).
- Keep the assembly a **labeled Compound** (don't fuse) so a part can be swapped
  and re-refined without rebuilding everything.
- Segment on real component boundaries; over-segmenting (one clip per feature of a
  single part) just adds overhead — use `kind:"feature"` sub-segments only when a
  single part is itself very complex.
