# Reusable build123d patterns for reconstructing CAD from video

Drop-in helpers proven on a full airliner reconstruction. They cover the
constructions most CAD tutorials use: bodies of revolution, lofted section
surfaces (wings/blades/nacelles/fins), symmetry, and engraved/patterned detail.
Adapt parameter names to the part. Run generation through the `cad` skill's
`scripts/step`; set `PYTHONPATH=<cad-skill>/scripts/packages/cadpy/src` if
`cadpy` won't import.

## Skeleton
```python
def gen_step():
    part = make_body()                        # one function per feature...
    part = part + make_feature_a()            # ...in the video's tree order
    part = part - cut_tool()                  # subtractive features
    # fillets LAST (fragile; every boolean invalidates selectors)
    part.label = "<part>"
    return part                               # a Solid, or a labeled Compound
```

## Body of revolution (revolve a closed half-profile)
```python
from build123d import BuildPart, BuildSketch, BuildLine, Plane, Axis, \
    Spline, Line, make_face, revolve

def make_body():
    profile = [(0,0), (100,60), (900,250), (2900,250), (4600,55)]  # (x, radius)
    with BuildPart() as p:
        with BuildSketch(Plane.XZ):
            with BuildLine():
                Spline(*profile)                 # nose->tail top curve
                Line(profile[-1], (4600, 0))     # close down to the axis
                Line((4600, 0), (0, 0))          # back along the axis
            make_face()
        revolve(axis=Axis.X)                     # 360° about X
    return p.part
```

## Hull / doubly-curved body by TWO-VIEW INTERSECTION (trace from ortho frames)
The most reliable way to match a hull, fuselage, or car body to a video: trace
the **side silhouette** and the **plan (top) outline** from the tutorial's
orthographic frames, then intersect the two extrusions. The result matches BOTH
views by construction — far closer than a guessed loft.
```python
from build123d import BuildPart, BuildSketch, BuildLine, Plane, Polyline, \
    make_face, extrude

BEAM = 11000
side = [(1400, 4300), (73500, 3600), (75000, 3600), (75000, 900),
        (18000, -1900), (600, 1200), (900, 3700)]      # (X, Z) traced profile
with BuildPart() as side_solid:
    with BuildSketch(Plane.XZ):
        with BuildLine(): Polyline(*side, close=True)
        make_face()
    extrude(amount=BEAM, both=True)                     # across the beam (Y)

# plan outline: bow point -> starboard side -> transom -> port side (NO repeated
# centreline points, or you get a zero-length edge and OCCT throws).
stbd = [(900,0),(30000,5500),(56000,5500),(75000,3740)]
plan = stbd + [(x,-y) for (x,y) in reversed(stbd[1:])]
with BuildPart() as plan_solid:
    with BuildSketch(Plane.XY):
        with BuildLine(): Polyline(*plan, close=True)
        make_face()
    extrude(amount=8000, both=True)                     # tall in Z
hull = side_solid.part & plan_solid.part               # intersection == hull
```
Two-tone waterline (e.g. red boot / grey topsides): intersect the hull with a big
box below Z=0 for the underwater body, subtract to get topsides, colour each, and
return a labeled `Compound([topsides, below_wl, superstructure])`.

## Two-radius teardrop airfoil (rounded LE AND TE)
The faithful version of the ubiquitous "circle + two tangent lines, trim"
airfoil. Use it for wings, stabilizers, fins, struts — anything with a rounded
leading edge tapering to a (rounded or sharp) trailing edge.
```python
import math
from build123d import BuildSketch, BuildLine, ThreePointArc, Line, make_face

def airfoil(chord, le_radius, te_radius):
    r1, r2, c = le_radius, te_radius, chord
    nx = (r1 - r2) / c
    ny = math.sqrt(max(0.0, 1 - nx*nx))          # external-tangent normal
    ta_u, ta_l = (r1*nx, r1*ny), (r1*nx, -r1*ny) # LE tangent points
    tb_u, tb_l = (c+r2*nx, r2*ny), (c+r2*nx, -r2*ny)  # TE tangent points
    with BuildSketch() as sk:
        with BuildLine():
            ThreePointArc(ta_u, (-r1, 0.0), ta_l)     # leading edge
            Line(ta_l, tb_l)                          # lower surface
            ThreePointArc(tb_l, (c+r2, 0.0), tb_u)    # trailing edge
            Line(tb_u, ta_u)                          # upper surface
        make_face()
    return sk.sketch
# sharp TE: pass a tiny te_radius, e.g. max(1.5, le_radius*0.06)
```

## Section planes and lofted surfaces
```python
from build123d import Plane, BuildPart, BuildSketch, loft, add

def span_plane(origin, normal=(0,1,0)):          # normal = span direction
    return Plane(origin=origin, x_dir=(1,0,0), z_dir=normal)  # local +x = chord

def lofted_surface(root, tip, normal=(0,1,0)):
    # root/tip = (origin, chord, le_r, te_r)
    with BuildPart() as p:
        with BuildSketch(span_plane(root[0], normal)):
            add(airfoil(root[1], root[2], root[3]))
        with BuildSketch(span_plane(tip[0], normal)):
            add(airfoil(tip[1], tip[2], tip[3]))
        loft()
    return p.part
# vertical fin: pass normal=(0,0,1) so sections stack in Z.
# sweep/dihedral come from offsetting the tip origin in X/Z.
```

## Circular nacelle (loft two circles) + pylon
```python
from build123d import Plane, BuildPart, BuildSketch, Circle, loft, Box, Pos

def nacelle(x1, y, z1, r1, x2, z2, r2):
    def rp(o): return Plane(origin=o, x_dir=(0,1,0), z_dir=(1,0,0))  # normal +X
    with BuildPart() as p:
        with BuildSketch(rp((x1,y,z1))): Circle(r1)     # inlet
        with BuildSketch(rp((x2,y,z2))): Circle(r2)     # exhaust (taper)
        loft()
    return p.part
# strut/pylon that MUST intersect the wing to fuse:
# pylon = Pos(x, y, z) * Box(length, width, tall_enough_to_overlap)
```

## Symmetry
```python
from build123d import mirror, Plane
port = mirror(starboard, about=Plane.XZ)   # Plane.XZ = the Y=0 symmetry plane
whole = body + starboard + port
```
Ensure mirrored/added sub-parts actually **overlap** the body (embed roots a few
mm inside) so `+` fuses them into one solid instead of a loose compound. Verify
with `inspect refs --facts` → `shapeCount: 1`.

## Engraved / patterned detail (windows, vents) — Wrap substitute
build123d has no `Wrap`; emulate an embossed/engraved row as shallow patterned
pocket cuts, then mirror.
```python
from build123d import BuildPart, BuildSketch, Plane, Rectangle, extrude
def window_row(n, pitch, x0, y_skin):
    tools = []
    for i in range(n):
        with BuildPart() as w:
            with BuildSketch(Plane(origin=(x0+i*pitch, y_skin, 78),
                                   x_dir=(1,0,0), z_dir=(0,1,0))):
                Rectangle(50, 75)              # exact on-screen window size
            extrude(amount=30, dir=(0,-1,0))   # cut into the skin
        tools.append(w.part)
    return tools
# for w in window_row(...): part = part - w - mirror(w, about=Plane.XZ)
```

## Sweep, shell, and patterns (common tree features)
```python
from build123d import (BuildPart, BuildLine, BuildSketch, Plane, Line, Spline,
    Circle, sweep, offset, mirror, Pos, Rotation, Location)

# Sweep: a section swept along a path (handrails, pipes, cable runs, keels)
with BuildPart() as p:
    with BuildLine() as path:
        Spline((0,0,0), (500,0,120), (1000,0,120))
    with BuildSketch(Plane.YZ):        # section in the plane normal to path start
        Circle(20)
    sweep(path=path.line)

# Shell / hollow: remove wall thickness, opening one or more faces
hollow = offset(solid, amount=-2.0, openings=solid.faces().sort_by(Axis.Z)[-1])

# Linear pattern (fuse if overlapping, else collect into a labeled Compound)
unit = Pos(0, 0, 0) * some_solid
row = unit
for i in range(1, 12):
    row = row + unit.moved(Location(Pos(i * 300, 0, 0)))

# Circular pattern
from build123d import PolarLocations
spokes = None
for loc in PolarLocations(radius=400, count=6):
    s = loc * spoke_solid
    spokes = s if spokes is None else spokes + s
```

## Fillets (last) and color
```python
from build123d import fillet, GeomType, Color
edges = part.edges().filter_by(GeomType.CIRCLE) \
            .filter_by(lambda e: e.center().X > 3500 and e.center().Z > 250)
if edges:
    part = fillet(edges, radius=20)            # target the junction you saw
part.color = Color(192/255, 192/255, 192/255)  # match the video's appearance
```

## Gotchas
- **`Pos()*Shape` inside a `with BuildPart()` context silently adds the shape at
  the ORIGIN and discards the `Pos`.** This piles every feature at (0,0,0) and
  produces a tiny/garbled part that renders as "exploded" once placed. Either use
  builder mode with `with Locations(x,y,z): Cylinder(...)`, or (cleaner for
  multi-feature parts) build in **algebra mode** — no `BuildPart`, just
  `part = Cylinder(...); part += Pos(x)*Cylinder(...); part -= Pos(y)*Box(...)`.
- **Algebra-mode accumulator must START from a real solid, not `Part()` or a
  located solid**, or `+` yields an unfused `ShapeList` (no `.bounding_box`, bad
  STEP). Seed with a bare `Cylinder(...)`/`Box(...)` at the origin, then `+=` the
  `Pos()*…` pieces. Verify with `type(part).__name__` == Solid/Compound and a
  sane `bounding_box()` BEFORE assembling.
- Fillet radius > local geometry → boolean failure. Keep fillets last and wrap in
  `try/except` so one bad edge doesn't kill the whole model.
- A "3-body" result usually means a sub-part didn't intersect the body — extend
  the strut/embed the root, don't force a compound.
- Reproduce **exact section shapes and dimensions**; reconstruct only the
  placement that the video's angled reference planes make ambiguous, and say so.
