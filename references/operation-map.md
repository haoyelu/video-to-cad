# CAD operation → build123d mapping

When you read a feature off the FeatureManager/history tree, translate it to the
build123d equivalent below. This keeps the code's operation order faithful to the
tree and prevents mis-modeling (e.g. rebuilding a Sweep as a Loft).

| Tutorial feature (SW / Fusion / Onshape) | build123d | Notes |
|---|---|---|
| Extrude Boss/Base, Extrude, Pad | `extrude(sketch, amount)` | `both=True` for symmetric; `dir=` for direction |
| Extruded Cut, Pocket, Hole | `part - extrude(...)` or `part - Hole/CounterBore...` | overshoot the tool ~1 mm past both faces |
| Revolve Boss/Base, Revolve | `revolve(profile, Axis.X, angle)` | closed half-profile touching the axis |
| Loft Boss/Base, Loft | `loft([sketchA, sketchB, ...])` | add sketches on their planes in order; guide curves are limited — approximate by section placement |
| Sweep, Swept Boss | `sweep(section, path)` | build the path with `BuildLine`; section normal to path start |
| Boundary Boss/Base | `loft(...)` (closest) | build123d has no true boundary; loft the boundary profiles |
| Fillet, Round | `fillet(edges, radius)` | LAST; select edges by `GeomType`/position, wrap in try/except |
| Chamfer | `chamfer(edges, length)` | same selection caution |
| Shell, Hollow | `offset(part, -t, openings=[faces])` or `Shell` | pick the removed faces by normal/position |
| Draft | build the taper into the sketch/loft | model a wider base + narrower top rather than a post-draft |
| Rib | thin `extrude` + intersect with the pocket wall | |
| Mirror (feature/body) | `mirror(obj, about=Plane.XZ/YZ/XY)` | choose the symmetry plane; embed to fuse |
| Linear Pattern | `for i: obj + obj.moved(Pos(i*pitch,...))` or `LinearPattern`-style loop | fuse if overlapping, else labeled compound |
| Circular Pattern | loop with `Rotation`/`PolarLocations` | |
| Wrap (emboss/deboss/scribe) | shallow patterned **pocket cuts** (no native Wrap) | see cad-patterns.md; note the substitution |
| Combine (add/subtract/common) | `+` / `-` / `&` | `&` = intersection (also the two-view hull trick) |
| Split (bodies) | `&` with half-space boxes | used for two-tone coloring at a waterline/plane |
| Dome | cap with a scaled `Sphere`/`Ellipsoid` section, fused | |
| Reference Plane (angle/offset) | `Plane(origin=..., x_dir=..., z_dir=...)` or `Plane.XY.offset(d)` | transcribe the reference, angle, and offset from the tree |
| Appearance / color | `shape.color = Color(r, g, b)` | set on each solid; split bodies for multi-tone |

## Ordering rules (mirror the tree)
- Base solid → major additive features → subtractive features → shell →
  through features → patterns/mirrors → **fillets/chamfers last**.
- Every boolean invalidates face/edge selectors, so re-select after each; don't
  hold indices across operations.
- If the tree shows a feature type build123d can't do natively (Wrap, true
  Boundary, Sweep with complex guide), pick the closest construction above and
  record the substitution in the caveats.
