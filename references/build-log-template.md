# Build-log template

Fill this in as `<part>_build_process.md`. Keep it a `state → timestamp` record:
every action tied to the video time at which that state appears, with exact
dimensions and (after the code exists) the generator function that reproduces it.

```markdown
# <Part> — CAD Build Process (timestamped)

**Source video:** <file or URL>
**Duration:** <MM:SS> · <WxH> · <fps>
**CAD software:** <e.g. SOLIDWORKS 2018> · Units <mm/in>
**Reconstructed as code:** <part>.py (build123d) → <part>.step

Timestamps come from a <INTERVAL>-second frame read, accurate to about
±<INTERVAL/2> s. The video opens with <intro/preview> and the real build runs
<MM:SS>–<MM:SS>. Each row: time — action — exact dimensions — code function.

## Timeline

### <N> — <FeatureName>: <what it is>  → `<code_function()>`
| Time | Action | Dimensions |
|---|---|---|
| MM:SS | <sketch plane / tool / operation> | <exact values: 250.00, R75.00, ⌀300, 45°> |
| ...   | ...                               | ... |

(repeat one section per feature, in build order)

## Final feature-tree order (as read on screen)
`Feature1 · Feature2 · Feature3 · ...`  → finish (color / rename)

## Notes / caveats
- Sampling resolution and ± tolerance.
- Values re-typed mid-edit (list initial → final; the final is authoritative).
- Numbers that are exact vs. reconstructed for proportion.
- Toolkit substitutions used in the code (e.g. pocket cuts for a Wrap feature).
```

## Rules
- One row per visible state; don't collapse multiple distinct dimensions into one.
- Preserve exact on-screen numbers.
- The feature-tree order is the authoritative operation order for the code.
- Note when a tutorial opens with a finished-model preview montage — those early
  timestamps are not part of the build and should be labeled as preview.
