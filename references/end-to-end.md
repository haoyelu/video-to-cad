# End-to-end: video link → interactive HTML

The full path from a video URL to an interactive 3D viewer (Assembly / Build
components / Run) + exploded view + build-and-assemble GIF. There is no single
push-button command: the middle stage (video → a faithful parametric model) is
the LLM reconstruction; the front (download) and back (viewer/animation) are
deterministic scripts.

```
<video link>
   │  yt-dlp / ffmpeg                                   [deterministic]
   ▼
 src.mp4
   │  video-to-cad reconstruction (this skill)          [LLM: perception+modeling]
   │    Mode A (one part) or Mode B (segment→build→compose, recursive)
   ▼
 parts/<id>.py  (parametric gen_step) + assembly kinematics
   │  viz_spec.py (thin mapping, ~30 lines)             [small LLM/human glue]
   ▼
 export_viz.py ──▶ viewer.json + GLBs + build steps + asm stages   [deterministic]
   ├─ make_animation.py ─▶ exploded.png + build_assemble.gif       [deterministic]
   └─ templates/viewer.html + viewer.json ─▶ interactive page       [deterministic]
```

## Option A — one ask (recommended)
Give the skill/agent the link: *"reconstruct this and generate the interactive
HTML."* It runs the whole chain and returns `web/viewer.html` (+ exploded/GIF).
Everything below is what it does under the hood — and how to re-run the
deterministic tail yourself.

## Option B — the commands
```bash
# 0) env
CAD=/Users/haoyelu/.agents/skills/cad
SK=/Users/haoyelu/.claude/skills/video-to-cad
export PYTHONPATH=$CAD/scripts/packages/cadpy/src        # use a python that has build123d

# 1) download                                            [deterministic]
yt-dlp --no-playlist -f "bestvideo[height<=720]+bestaudio/best" \
       --merge-output-format mp4 -o src.mp4 "<VIDEO_LINK>"

# 2) RECONSTRUCT (the LLM stage — run this skill on src.mp4)
#    Follow SKILL.md: extract frames -> read/transcribe features+dims ->
#    trace ortho views -> write parts/<id>.py (gen_step) -> compose ->
#    closed-loop refine.  For assemblies use Mode B (orchestration.md), recursive.
#    OUTPUT: parts/<id>.py (parametric) + the assembly placement/kinematics.

# 3) viz_spec.py  (thin per-asset mapping; example: skill_test/modeB/web/viz_spec.py)
#    PARTS = {id: gen_step}; INSTANCES = [{part,label,pos,rot_deg,color}];
#    optional STAGES, BUILD (per-feature), MOTION.  See references/visualization.md.

# 4) trajectory -> GLBs + viewer.json                    [deterministic]
python $SK/scripts/export_viz.py viz_spec.py --out web

# 5) animations (optional)                               [deterministic]
python $SK/scripts/make_animation.py web                 # -> web/exploded.png + web/build_assemble.gif

# 6) interactive HTML                                    [deterministic]
cp $SK/templates/viewer.html web/
cd web && python3 -m http.server 8099                    # open http://127.0.0.1:8099/viewer.html
```

## Which steps need an LLM
| Step | LLM? |
|---|---|
| 1 download, 4 export, 5 animate, 6 viewer | No — deterministic scripts |
| 2 reconstruct (segment, read dims, choose ops, write generators, mates, refine) | **Yes** — perception + judgment |
| 3 `viz_spec` (and any new `MOTION` mechanism model) | Small LLM/human glue |

The LLM cost is front-loaded into step 2 (pixels → parametric model). Once that
model exists, steps 4–6 regenerate all artifacts with fixed commands.

## Caveats
- The HTML's fidelity/scope follows the reconstruction (clean short part vs. a
  3-hour multi-part assembly → primary-form tier; see orchestration.md).
- The viewer's **Run** needs a `MOTION` block (`crank_slider` / `spin` / null).
  Without one, Run just auto-rotates.
- Servers started with `http.server` are temporary; re-serve the `web/` folder to
  reopen. For a portable single file, inline the GLBs as base64 in the HTML.
- Interpreter: run the scripts with a python that has `build123d` (often anaconda
  base), not a bare `python3`, and keep the `PYTHONPATH` above set.
