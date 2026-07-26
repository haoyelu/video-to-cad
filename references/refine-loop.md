# Closed-loop component refinement (RL-style)

Reconstruction quality comes from **iteration against a reward**, not from one
lucky pass. Treat every component as a small optimization loop: the model is the
*policy* (it edits parameters), the video frame is the *reference*, and a
*reward* (silhouette IoU + the fidelity rubric) tells you whether the last edit
helped. Keep taking the edit that raises the reward until the component aligns
with the video. This is RL-shaped iterative refinement — no weight training, the
model-in-the-loop is the optimizer.

## The per-component loop
For each component (a part, then a sub-assembly, then the whole model):

```
target = trace/select the reference frame(s) for THIS component (matched view)
best = -1 ; stale = 0
for step in range(MAX_STEPS):            # MAX_STEPS ~ 4-6
    generate  -> python <cad>/scripts/step <component>.py
    render    -> snapshot from the camera that matches `target`
    reward    -> r = silhouette_iou(target, render)          # objective
                 + rubric grade (proportion/features/dims)   # model's eyes
    if r >= 0.85 and rubric passes:  break        # aligned -> stop
    if r <= best + 0.01:  stale += 1              # no real gain
    else:                 best = r ; stale = 0
    if stale >= 2:  break                          # converged / stuck -> stop
    diagnose the SINGLE worst mismatch (one axis: bow too blunt, deck too
      high, feature missing, wrong proportion) and edit the ONE parameter that
      fixes it. One change per step so the reward attributes cleanly.
report: final reward, what converged, what remains (honest gap).
```

Reward signal:
- **Objective:** `scripts/silhouette_score.py REF.png RENDER.png [--ref-bbox …]`
  → `silhouette_iou`. Compare the SAME view; crop the reference to the model.
  Convention: ≥0.85 aligned · 0.70–0.85 close · <0.70 revise.
- **Rubric (model's judgement):** the step-7 fidelity checklist in SKILL.md
  (silhouette, proportion, feature completeness, construction match, dims,
  appearance). IoU can't see internal features or a wrong operation — the rubric
  catches those.
- Use both; neither alone is sufficient. Never call a component done on IoU
  alone (a blob can score high) or on "looks right" alone (proportions drift).

## Recursion / hierarchy (build bottom-up, refine at each level)
```
for each PART:            run the loop vs the part's reference frame
for each SUB-ASSEMBLY:    run the loop vs its reference (parts now frozen)
for the WHOLE model:      run the loop vs the final render/ortho views
```
A part that fails its own loop can't be fixed at assembly level — converge parts
first. Only unfreeze a part if the assembly loop proves the part's reference was
misread.

## Parallelize with subagents (one refiner per component)
For a multi-part model, spawn one `general-purpose` refiner per part, each
running its own closed loop and returning converged parameters + final reward:

> "Refine `make_piston()` against `frames/piston_side.png`. Loop up to 5 times:
>  generate, render matched view, score with silhouette_score.py + the rubric,
>  edit ONE parameter toward the reference, repeat until iou≥0.85 or no gain for
>  2 steps. Return the final parameter values, the final iou, and the residual
>  mismatch."

Then a synthesis step assembles the converged parts and runs the assembly-level
loop. This is the fan-out/verify pattern applied to CAD: independent per-part
optimization, then joint refinement.

## Skill-level learning (the outer loop)
When a refinement reveals a *systematic* miss — a construction that never matches
(guessed proportions vs traced ortho views), an API error in a template, a
missing operation mapping — don't just fix the one model: **update the skill**
(add the rule to `cad-patterns.md` / `operation-map.md`, fix the script, tighten
SKILL.md). The skill is the durable policy; each run should leave it better, so
the next reconstruction starts closer. (This file, the two-view-hull method, the
keyframe-timestamp fix, and the assembly patterns all came from that outer loop.)

## Stopping rules (don't spin)
- Stop a component loop at reward ≥ threshold, at MAX_STEPS, or after 2 steps
  with no gain — report the residual gap honestly instead of grinding.
- If the reference itself is ambiguous (dimension never shown, view never
  orthographic), say so and stop; more iterations can't recover missing info.
