"""Trajectory -> visualization assets (generic).

Turn a reconstruction's parametric model into everything the animations and the
interactive viewer need: per-part GLBs (local frame), optional per-feature build
GLB/STEP sequences, cumulative assembly STEP stages, and a single `viewer.json`
manifest consumed by templates/viewer.html and scripts/make_animation.py.

You supply a small **viz spec** Python module (thin, reuses your part generators
+ your assembly kinematics). Required/optional attributes:

    TITLE  = "4-Cylinder Engine"          # optional
    UNITS  = "mm"                          # optional (default mm)
    # distinct part meshes, local frame — id -> zero-arg callable returning a solid
    PARTS  = {"crankshaft": crankshaft.gen_step, "piston": piston.gen_step, ...}
    # assembly placement — one row per instance
    INSTANCES = [
        {"part":"crankshaft","label":"crankshaft","pos":(0,0,0),"rot_deg":(0,0,0),"color":"#9ea3aa"},
        {"part":"connecting_rod","label":"conrod_cyl1","pos":(-157.5,0,44),"rot_deg":(0,0,0),"color":"#b98f4d"},
        ...
    ]
    # OPTIONAL assemble-one-by-one grouping (list of instance-label groups, in order)
    STAGES = [["crankshaft"], ["conrod_cyl1","rodcap_cyl1","wristpin_cyl1","piston_cyl1","ring1_cyl1",...], ...]
    # OPTIONAL per-feature build — id -> list of (feature, operation, params_dict, solid)
    BUILD = {"piston": [("Boss-Extrude1","extrude",{"OD_mm":85},solid1), ...], ...}
    # OPTIONAL declarative motion model for the viewer "Run" (see visualization.md)
    MOTION = {"type":"crank_slider", ...}   # or {"type":"spin",...} or omit

Usage:
    python export_viz.py path/to/viz_spec.py --out path/to/web
Writes: <out>/parts/*.glb, <out>/build_steps/*.{glb,step}, <out>/asm/*.step,
        <out>/viewer.json
"""
import argparse, importlib.util, json, os, sys


def _load(spec_path):
    spec = importlib.util.spec_from_file_location("viz_spec", spec_path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(os.path.abspath(spec_path)))
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from build123d import export_gltf, export_step, Compound, Location
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # for build_recorder
    from build_recorder import BuildRecorder

    m = _load(a.spec)
    out = os.path.abspath(a.out)
    for sub in ("parts", "build_steps", "asm"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    units = getattr(m, "UNITS", "mm")

    # 1) distinct part meshes (local frame) -> parts/<id>.glb ; keep solids for asm
    solids, parts_man = {}, []
    for pid, fn in m.PARTS.items():
        s = fn(); solids[pid] = s
        rel = f"parts/{pid}.glb"
        export_gltf(s, os.path.join(out, rel), binary=True)
        parts_man.append({"id": pid, "glb": rel})
    print(f"parts: {len(parts_man)}")

    # 2) per-feature build sequences (optional) -> build_steps/ + steps in manifest
    build_man = []
    for cid, feats in getattr(m, "BUILD", {}).items():
        rec = BuildRecorder(cid, os.path.join(out, "build_steps"),
                            units=units, glb=True)
        for (feature, op, params, solid) in feats:
            rec.step(solid, feature, op, params)
        rec.save()
        steps = [{"step": s["index"], "feature": s["feature"], "operation": s["operation"],
                  "params": s["parameters"],
                  "glb": f"build_steps/{s['glb']}" if s.get("glb") else None,
                  "step_file": f"build_steps/{s['step_file']}" if s.get("step_file") else None}
                 for s in rec.steps]
        build_man.append({"id": cid, "title": cid.replace("_", " ").title(), "steps": steps})
        print(f"build[{cid}]: {len(steps)} features")

    # 3) instances (assembly placement) + cumulative assembly STEP stages
    inst_by_label = {i["label"]: i for i in m.INSTANCES}
    def placed(inst):
        return solids[inst["part"]].moved(Location(tuple(inst["pos"]),
                                                    tuple(inst.get("rot_deg", (0, 0, 0)))))
    stages = getattr(m, "STAGES", None) or [[i["label"]] for i in m.INSTANCES]
    asm_man, acc = [], []
    for k, group in enumerate(stages):
        acc += [placed(inst_by_label[l]) for l in group]
        rel = f"asm/asm_{k:02d}.step"
        export_step(Compound(children=list(acc)), os.path.join(out, rel))
        asm_man.append({"stage": k, "labels": group, "step_file": rel})
    print(f"assembly stages: {len(asm_man)}")

    # 4) viewer.json
    viewer = {
        "title": getattr(m, "TITLE", "Assembly"), "units": units,
        "parts": parts_man,
        "instances": [{"part": i["part"], "label": i["label"], "pos": list(i["pos"]),
                       "rot_deg": list(i.get("rot_deg", (0, 0, 0))),
                       "color": i.get("color", "#b8bcc2")} for i in m.INSTANCES],
        "build": build_man,
        "assembly_stages": asm_man,
        "motion": getattr(m, "MOTION", None),
    }
    with open(os.path.join(out, "viewer.json"), "w") as fh:
        json.dump(viewer, fh, indent=2)
    print(f"wrote {out}/viewer.json")


if __name__ == "__main__":
    main()
