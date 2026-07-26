# Frame-reader subagent prompt (reuse verbatim, edit the range)

Split the detail-pass frames across several `general-purpose` subagents (about
35 frames each) launched in ONE message so they run concurrently. Give each this
prompt, filling in the assigned frame range and what that range covers.

---

You are analyzing frames from a CAD tutorial screencast. Frames are in
`<ABSOLUTE_FRAMES_DIR>/` named `f_0001.jpg ... f_NNNN.jpg`. Frame `d_N`
corresponds to video time `t = (N-1) * <INTERVAL> seconds`.

Your assigned range: **f_<START> through f_<END>** (video <MM:SS>–<MM:SS>).
This covers **<what this range builds: e.g. the fuselage revolve / the wing loft>**.

Read EVERY frame in your range with the Read tool (in batches of 6–8). For each
meaningful state, record:
1. Video timestamp (MM:SS).
2. The exact feature/tool active — from the title bar (e.g. "Sketch7 of Part4"),
   the PropertyManager/panel heading, and the ribbon button.
3. EVERY numeric dimension visible — read precisely (e.g. `250.00`, `R75.00`,
   `⌀300`, `45.00deg`, offset distances). Exact numbers are the most important
   output; do not round or paraphrase.
4. The sketch plane / reference used and how each datum plane was defined
   (reference, angle, offset distance).
5. Construction details: spline vs arc vs line; circle+tangent-line airfoil;
   loft/revolve/extrude/sweep; relations (Tangent/Symmetric/Equal); guide
   curves; patterns; wraps; mirrors; fillets; the number of loft profiles.
6. Any detail a coarse review would miss: rounded trailing edges, double arcs,
   pylons, inlet/exhaust taper, guide-curve sweeps, exact window size/count/
   pitch, fillet target edges, final color, part rename.
7. **The FeatureManager / history tree (left panel).** Whenever the tree is
   legible, transcribe the feature names in order (`Revolve1`, `Loft3`,
   `Mirror2`, `LPattern1`, `Wrap1`, `Fillet6`, `Plane8`…). In a time-lapse the
   action is often off-camera, but the tree still reveals the exact operation,
   its type, and its order — this is the authoritative operation list. Note the
   frame where you read the fullest tree.

Be precise and exhaustive about numbers. Distinguish transient drag readouts
(pre-dimension values) from final committed dimensions.

Return a compact chronological list: `timestamp — feature — [exact dims] — notes`.
At the end add a **"DETAILS POSSIBLY MISSED"** section, and quote the fullest
on-screen **feature-tree order** you saw (with the frame/timestamp you read it
from).
