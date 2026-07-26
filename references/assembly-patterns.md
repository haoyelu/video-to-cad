# Multi-part assembly patterns (mechanical assemblies)

When the tutorial builds several parts and mates them (engine, gearbox, robot,
enclosure with hardware), reconstruct it as a **labeled assembly**, not one
fused blob. Use `cadpy.assembly.AssemblyHelper`, which records semantic mates and
realizes them with native build123d joints. Verified against build123d 0.10.0.

## Decompose from the tutorial's own structure
The tutorial usually names the parts for you — separate part files and the
assembly (Assem1) FeatureManager tree list every component. Transcribe that list;
it is your part inventory and your assembly order.
Example (4-cylinder engine): `crankshaft, piston, piston ring, connecting rod,
connecting rod cap, piston pin` → one `make_*()` per part.

## Structure: parts → frames → mates → build
```python
from build123d import BuildPart, Cylinder, Box, Axis, Location, Color, Mode
from cadpy.assembly import AssemblyHelper

def make_crankshaft(): ...        # each part is part-local: origin on its
def make_piston():     ...        # mating datum, a clear axis convention
def make_conrod():     ...

def gen_step():
    asm = AssemblyHelper("engine")
    crank = asm.add(make_crankshaft(), "crankshaft", color=Color(.55,.57,.60))
    # first part added = the fixed root; everything mates relative to it.

    # a motion joint datum (rotating crank about +X):
    asm.revolute_frame(crank, "crank_axis", Axis((0,0,0),(1,0,0)))

    rod = asm.add(make_conrod(), "conrod_cyl1", color=Color(.72,.55,.30))
    # define a frame on each side of the mate, then connect (FIXED first):
    target = asm.rigid_frame(crank, "pin1", Location((x,y,z),(beta,0,0)))
    rodfrm = asm.rigid_frame(rod,   "big_end", Location((0,0,0)))
    asm.connect(target, rodfrm, relation="rigid", label="rod_on_pin1")
    return asm.build()            # returns a labeled Compound assembly
```
Key facts (from `cad` skill `positioning.md`, confirmed):
- `add(shape, name, color=…)` → handle; **first add is the fixed root**.
- `rigid_frame(part, name, Location(pos,(rx,ry,rz)))` → a MateTarget. A rigid
  frame fully constrains position AND orientation — the robust default; prefer it
  over `coaxial` when a part could otherwise spin about the mate axis.
- `connect(fixed, moving, relation="rigid", label=…)` seats `moving` so its frame
  coincides with `fixed`'s. Fixed-first, always.
- `coaxial(fixed, moving, offset=…)` / `face_to_face(...)` for axis-alignment /
  flush seating; `revolute_frame(part,name,Axis)` / `linear_frame` / `cylindrical_frame`
  for motion datums. Frames/targets can be a MateTarget or a `(part,"framename")`
  tuple.
- `add_module(name, children, color=…)` groups a functional unit (one cylinder,
  a bearing) into a sub-assembly node so nested occurrence refs stay meaningful.

## Repetition (patterned components)
Loop the mate, don't copy-paste. Compute each instance's placement from
parameters (bore pitch, throw angle, firing order) and give each a role label:
```python
ANGLES = [0,180,180,0]                     # inline-4 crank throws
for i in range(4):
    x = (i-1.5)*PITCH
    rod = asm.add(make_conrod(), f"conrod_cyl{i+1}", color=BRONZE)
    pis = asm.add(make_piston(), f"piston_cyl{i+1}", color=ALLOY)
    ... define frames from the per-cylinder kinematics; connect ...
```
Labels like `piston_cyl3` keep viewer/inspection occurrence refs traceable.

## Validate the assembly (not just "it built")
```bash
python <cad>/scripts/step engine.py
python <cad>/scripts/inspect refs engine.step --facts --positioning
#   expect kind: assembly, the right leafOccurrenceCount (one per part instance)
python <cad>/scripts/inspect measure engine.step --from '#a' --to '#b' --axis z
#   e.g. rod big-end axis vs crank-pin axis distance ~ 0 for a seated mate
```
Report mates as "checked" only if you measured them; otherwise say "not checked".

## Gotchas
- **Reconcile shared mating dimensions across independently-built parts.** Parts
  built in parallel often disagree on a dimension they must share (a raceway, a
  bore/pin fit, a bolt circle, a pitch radius) because each builder read it from
  its own clip. BEFORE composing, check the mating dims are self-consistent (e.g.
  outer_raceway − inner_raceway == roller_dia) and fix the offending part's
  parameter to one coherent set — never assume they fit. Declaring the interface
  dims up front (see orchestration.md `interfaces`) prevents most of this.
- A part built off its mating datum makes every mate an awkward transform — put
  each part's origin ON its mate face/axis first.
- `connect` with `rigid` needs both frames' orientations right; if a part lands
  rotated, fix the Euler angles in its `rigid_frame` Location, not by nudging.
- Don't fuse the assembly into one solid — keep it a labeled Compound so parts
  stay individually selectable and you can refine one part at a time (see
  `refine-loop.md`).
- The exported STEP holds the resolved static placement + native labels, not live
  constraints; re-running the generator recomputes placement from parameters.
