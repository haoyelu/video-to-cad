# Model routing — cheap vs. frontier per stage

Quality-first cost optimization. Every stage of this pipeline that needs an LLM
was benchmarked against cheap/open models (via OpenRouter) and frontier models.
The result: a **hybrid** is both affordable and faithful — route each stage to
the cheapest model that clears its bar, and keep frontier only where cheap models
provably fail. A fully-cheap end-to-end run is NOT reliable (errors compound:
a vision misread feeds an unrepairable code error), so do not swap wholesale.

## The routing table

| Pipeline stage | Route to | Why |
|---|---|---|
| Segment / decompose the video (Mode B tree) | **cheap** — qwen3-vl-8b, qwen3.6-flash, gemini-flash-lite | trivially handled; all cheap models list parts + relationships correctly |
| Read dimensions from frames (perception) | **cheap, but TWO readers + reconcile** — llama-4-scout (best recall) + qwen3-vl-8b | recall problem, not a capability cliff: no cheap model exceeds ~12/16 on a dense sheet, but two readers with *different* misses recover most of it via the two-reader reconcile (step 3) + two-view intersection (step 2b) |
| Easy code-gen (extrude / hole / prism / boss) | **cheap** — qwen3.6-flash (PASS r1), qwen3-vl-8b, deepseek-v3.1 | simple build123d compiles first or second try |
| **Hard code-gen — revolve, loft, sweep, `AssemblyHelper` mates** | **FRONTIER** (Opus / Sonnet) | every cheap/open model failed revolve + assembly-mates in the repair loop; only loft was occasionally solved. This is the #1 quality seam |
| **Mate / reconcile assembly** (joints + cross-part interface dims) | **FRONTIER** | relational reasoning over the whole part set at once + numeric conflict resolution; cheap models can *describe* the assembly but can't emit correct joint code |
| **Refine loop** (silhouette-IoU + rubric → diagnose → self-repair) | **FRONTIER** | needs visual judgment + targeted parameter edits that converge; cheap models misjudge and drift instead of converging |

## How to apply it

- **Default runs (single tractable part, Mode A):** cheap models handle acquire →
  read → easy code-gen. Escalate to frontier only if the part needs revolve/loft
  (bodies of revolution, wings/blades/hulls) — which most real parts do, so in
  practice frontier writes the generator and cheap models do perception.
- **Assemblies (Mode B):** cheap models segment the tree and read each leaf's
  dimensions; **frontier** writes any revolve/loft generator, does the
  `compose`/mate/reconcile step, and drives the refine loop.
- **Two-reader reconcile (the cheap-vision trick):** for each dimension-dense
  frame, ask two *different* cheap vision models, then union their reads and
  resolve conflicts (prefer the value that is internally consistent with the
  part's other dims / the interface it mates to). This closes most of the gap to
  frontier vision at a fraction of the cost.
- **Never economize on** revolve/loft/assembly code-gen or the refine loop. That
  is where "looks like CAD" becomes "looks like *this video's* part."

## Model notes (OpenRouter, as benchmarked)
- **qwen3-vl-8b-instruct** — best cheap vision (8/16 dense), PASS-r1 easy code. Use
  as the second vision reader and for easy generators.
- **llama-4-scout** — best value vision recall (12/16 dense) but fails code-gen.
  Use as the *primary* vision reader only.
- **qwen3.6-flash** — solid all-rounder: 6/16 vision, PASS-r1 easy code, PASS-r1
  loft. Best single cheap model if you must pick one.
- **deepseek-v3.1** — strongest cheap coder (PASS-r2 easy, PASS-r2 loft, came
  closest on revolve/assembly but still didn't cleanly pass). Good escalation
  step *below* frontier for borderline geometry.
- **Avoid:** qwen3-vl-32b (hallucinated, 1/16), qwen3.5 line and most `-a3b`/`-9b`
  variants (empty/errored on OpenRouter), kimi-k3 / kimi-k2.7-code (errored /
  empty), gpt-5-nano / gpt-5.1-codex-mini (empty via OpenRouter routing).

Findings are approximate and provider-routing-dependent; re-benchmark before
relying on a specific cheap model for a production run.
