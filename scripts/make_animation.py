"""Generic animation compositor: viewer.json -> exploded still + two-act GIF
(Act 1 = each component built feature-by-feature in a grid; Act 2 = cumulative
assembly one stage at a time). Renders the recorded STEP stages via the cad
skill's snapshot tool, then composites with PIL + ffmpeg. No per-asset code.

Usage:
  make_animation.py <dir-with-viewer.json> [--cad-skill PATH] [--camera 35:25]
                    [--fps 7] [--width 1000]
Outputs (next to viewer.json): exploded.png, build_assemble.gif
"""
import argparse, json, os, re, subprocess, sys, glob, tempfile

CAD_DEFAULT = "/Users/haoyelu/.agents/skills/cad"


def render(step_path, cad, camera, extra=None):
    """Render a STEP via the cad snapshot tool; return the PNG path."""
    env = dict(os.environ, PYTHONPATH=f"{cad}/scripts/packages/cadpy/src")
    tmp = os.path.join(tempfile.gettempdir(), "mkanim_x.png")
    cmd = ["python", f"{cad}/scripts/step".replace("step", "snapshot"),
           "--input", step_path, "--output", tmp, "--camera", camera]
    if extra:
        cmd += extra
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    mo = re.search(r"saved snapshot: (\S+)", r.stdout + r.stderr)
    return mo.group(1) if mo else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir"); ap.add_argument("--cad-skill", default=CAD_DEFAULT)
    ap.add_argument("--camera", default="35:25"); ap.add_argument("--fps", type=int, default=7)
    ap.add_argument("--width", type=int, default=1000)
    a = ap.parse_args()
    from PIL import Image, ImageDraw, ImageFont
    D = os.path.abspath(a.dir)
    vj = json.load(open(os.path.join(D, "viewer.json")))
    cad = a.cad_skill
    try:
        F = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        FS = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 15)
    except Exception:
        F = FS = ImageFont.load_default()
    W, H, BG = a.width, int(a.width*0.72), (238, 242, 248)
    def ct(d, cx, y, t, f, fill=(40, 44, 52)):
        b = d.textbbox((0, 0), t, font=f); d.text((cx-(b[2]-b[0])/2, y), t, font=f, fill=fill)

    def render_step(sf):
        p = render(os.path.join(D, sf), cad, a.camera)
        return Image.open(p).convert("RGB") if p and os.path.exists(p) else None

    # ---- Act 1: build grid ----
    comps = vj.get("build", [])
    imgs = {}  # (cid, idx)->Image
    for c in comps:
        for s in c["steps"]:
            if s.get("step_file"):
                imgs[(c["id"], s["step"])] = render_step(s["step_file"])
    frames = []
    if comps:
        cols = 2; rows = (len(comps)+1)//2
        cw, ch = W//cols, (H-40)//rows
        maxs = max(len(c["steps"]) for c in comps)
        for t in range(1, maxs+1):
            img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
            ct(d, W/2, 6, "1.  Each component — built feature by feature", F)
            for i, c in enumerate(comps):
                r, cc = divmod(i, cols); x0 = cc*cw; y0 = 40+r*ch
                k = min(t, len(c["steps"])); s = c["steps"][k-1]
                im = imgs.get((c["id"], s["step"]))
                if im:
                    th = im.copy(); th.thumbnail((cw-16, ch-40))
                    img.paste(th, (int(x0+(cw-th.width)/2), int(y0+(ch-40-th.height)/2)))
                ct(d, x0+cw/2, y0+ch-34, c["title"], FS)
                ct(d, x0+cw/2, y0+ch-18, f"{k}/{len(c['steps'])} · {s['feature']}", FS, (90, 90, 96))
            frames += [img]*(8 if t == maxs else 6)

    # ---- Act 2: cumulative assembly ----
    for k, st in enumerate(vj.get("assembly_stages", [])):
        im = render_step(st["step_file"]);
        img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
        ct(d, W/2, 6, "2.  Assembled one stage at a time", F)
        if im:
            th = im.copy(); th.thumbnail((W-60, H-90))
            img.paste(th, (int((W-th.width)/2), int(44+(H-84-th.height)/2)))
        cap = ", ".join(st["labels"]) if len(st["labels"]) <= 3 else f"stage {k+1}"
        ct(d, W/2, H-34, ("+ " + cap) if k else cap, FS, (20, 90, 40))
        frames += [img]*(10 if k == len(vj["assembly_stages"])-1 else 7)

    # ---- exploded still (final assembly, radial-ish along Z) ----
    if vj.get("assembly_stages"):
        final = vj["assembly_stages"][-1]["step_file"]
        disp = '{"mode":"rendered","exploded":{"enabled":true,"axis":"z","spacing":1.6}}'
        ep = render(os.path.join(D, final), cad, a.camera, ["--display", disp])
        if ep and os.path.exists(ep):
            Image.open(ep).convert("RGB").save(os.path.join(D, "exploded.png"))
            print("wrote exploded.png")

    # ---- encode GIF ----
    if frames:
        tmp = tempfile.mkdtemp()
        for i, f in enumerate(frames):
            f.save(os.path.join(tmp, f"g_{i:03d}.png"))
        gif = os.path.join(D, "build_assemble.gif")
        pal = os.path.join(tmp, "pal.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(a.fps),
                        "-i", f"{tmp}/g_%03d.png", "-vf", "palettegen=stats_mode=full", pal])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(a.fps),
                        "-i", f"{tmp}/g_%03d.png", "-i", pal, "-lavfi", "paletteuse=dither=bayer",
                        "-loop", "0", gif])
        print(f"wrote {gif} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
