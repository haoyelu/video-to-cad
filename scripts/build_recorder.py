"""Reusable parametric build-step recorder (engineering record).

Wrap a part's construction so every feature is recorded step by step, in build
order, as a PARAMETRIC + TRACEABLE record: each step logs its operation, its
driving parameters (named dimensions), the sketch plane/datum, and verification
metrics (bounding box, volume) of the cumulative solid, plus an optional STEP
export. `save()` writes a machine-readable feature-tree JSON (a rebuildable
design table) so the record is a spec, not just pictures.

Usage:
    from build_recorder import BuildRecorder
    rec = BuildRecorder("piston", outdir, units="mm", datum="piston center",
                        axis="+Z (bore axis +X)")
    p = make_body();       rec.step(p, "Boss-Extrude1", "extrude",
                                    {"OD": 85, "H": 90}, sketch="Front")
    p -= groove;           rec.step(p, "Cut-Extrude1", "cut",
                                    {"root_D": 79, "width": 4.30, "z_off": 7.30})
    ...
    rec.save()             # -> outdir/piston.record.json

No renderer is needed; this is pure geometry + metadata (cheap, deterministic).
Render the per-step STEP files separately if a visual is wanted.
"""
import os
import json


class BuildRecorder:
    def __init__(self, name, outdir, *, units="mm", datum="", axis="",
                 export=True, glb=False):
        self.name = name
        self.outdir = outdir
        self.units = units
        self.datum = datum
        self.axis = axis
        self.export = export
        self.glb = glb              # also export a GLB per step (for web viewer)
        self.steps = []
        os.makedirs(outdir, exist_ok=True)

    def step(self, solid, feature, operation, parameters=None, *,
             sketch=None, export=None):
        """Record one feature. `solid` = the CUMULATIVE result after this feature.
        Returns `solid` so calls can chain."""
        i = len(self.steps) + 1
        rel = f"{self.name}_s{i:02d}_{feature}.step"
        do_export = self.export if export is None else export
        glb_rel = None
        if do_export:
            from build123d import export_step
            export_step(solid, os.path.join(self.outdir, rel))
            if self.glb:
                from build123d import export_gltf
                glb_rel = f"{self.name}_s{i:02d}_{feature}.glb"
                try:
                    export_gltf(solid, os.path.join(self.outdir, glb_rel), binary=True)
                except Exception:
                    glb_rel = None
        bb = solid.bounding_box()
        try:
            vol = round(float(solid.volume), 3)
        except Exception:
            vol = None
        self.steps.append({
            "index": i,
            "feature": feature,
            "operation": operation,          # extrude / revolve / cut / pattern / fillet / chamfer / mirror
            "sketch_plane": sketch,
            "parameters": parameters or {},   # named driving dimensions
            "bbox_mm": [round(bb.min.X, 3), round(bb.min.Y, 3), round(bb.min.Z, 3),
                        round(bb.max.X, 3), round(bb.max.Y, 3), round(bb.max.Z, 3)],
            "size_mm": [round(bb.size.X, 3), round(bb.size.Y, 3), round(bb.size.Z, 3)],
            "volume_mm3": vol,
            "step_file": rel if do_export else None,
            "glb": glb_rel,
        })
        return solid

    def save(self, path=None):
        """Write the feature-tree JSON (the traceable design table)."""
        doc = {
            "component": self.name,
            "units": self.units,
            "datum": self.datum,
            "axis": self.axis,
            "n_features": len(self.steps),
            "features": self.steps,
        }
        path = path or os.path.join(self.outdir, f"{self.name}.record.json")
        with open(path, "w") as fh:
            json.dump(doc, fh, indent=2)
        return path
