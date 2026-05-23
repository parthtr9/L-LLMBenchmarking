---
name: longevitybench-design
description: Use this skill to generate well-branded interfaces and assets for LongevityBench (by SD hackers), the LLM benchmarking dashboard for Insilico Medicine's longevity-tuned L-LLM. Use for production code or throwaway prototypes/mocks. Contains essential design guidelines, colors, type, fonts, assets, science icons, and UI kit components for prototyping.
user-invocable: true
---

Read the `README.md` file within this skill, then explore the other available files:

- `colors_and_type.css` — token system: colors (Insilico-green ramp, neutrals, semantic, data-viz palette), DM Sans + JetBrains Mono type, spacing (4px grid), radii, shadows, motion. Import this in every new file.
- `assets/` — Insilico Medicine brand marks (badge, logo, Pharma.ai, PandaOmics, inClinico). Copy out, don't link cross-origin.
- `preview/` — small reference cards for every primitive. Useful as visual specimens.
- `ui_kits/longevity_bench/` — the live React dashboard. Three primary views in order of demo importance: **Trust & reasoning** (default) → **Compare models** → **Live runs**. Reusable JSX components: `Sidebar`, `TopBar`, `TrustView`, `CompareView`, `LiveRunsView`, `RunDetail`, `RecordDrawer`, `NewRunModal`, plus primitives (`Icon`, `Button`, `Badge`, `Pill`, `MetricCard`).

**If creating visual artifacts** (slides, mocks, throwaway prototypes), copy assets out and create static HTML files for the user to view. Link `colors_and_type.css` from the file. For Insilico-style brand fidelity, lean on:
- Green only for primary action / success / focus / brand. Most of the UI stays neutral on white.
- DM Sans 500 (NOT bold) with tight letter-spacing for headings.
- JetBrains Mono for gene symbols, IDs, scores, and tabular numbers.
- Sharp radii (2–8px), barely-there shadows, 1px hairline borders. No glassmorphism, no gradient backgrounds, no emoji.

**If working on production code**, copy assets and read the rules to become an expert in designing with this brand. The CONTENT FUNDAMENTALS section in README has voice/tone rules — follow them.

**If the user invokes this skill without other guidance**, ask them what they want to build or design (a slide deck? a screen mock? a leaderboard? a paper figure?), confirm the audience (researchers vs. judges vs. internal team), then act as an expert designer who outputs HTML artifacts or production code, depending on the need.

Domain note: this is a benchmarking instrument for longevity-science LLMs. Audience is researchers; tone is sober and evidence-first. No marketing intensifiers, no exclamation marks, no emoji. Lean on numbers, CIs, baselines.
