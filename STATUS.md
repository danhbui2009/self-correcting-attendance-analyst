# Module 2 status

## Portfolio packaging gates (2026-10-02)
- **Gate 1 — Case study: PASS.** README is a seven-section client-facing case study and `PORTFOLIO_DESCRIPTION.md` contains a 113-word portfolio blurb. Independent read-only review checked the copy, four outcomes, local links, and diagram; its CLI/UI branch correction was applied.
- **Gate 2 — Reproducibility: PASS for a fresh Python 3.11 virtual environment on this Windows host.** Installation, CLI figures, 88 tests, 18 UI AppTests, local Streamlit health, controlled abstention, and dependency health passed from a source copy without the prior `.venv`. See `TEST_REPORT.md`. A separate clean machine/public download has not been tested.
- **Gate 3 — Demo evidence: PASS locally.** `portfolio/demo_walkthrough_user_voice.mp4` is a 2:17 recording of the running Streamlit UI with the user's four voice recordings in order 6 → 8 → 9 → 10. Four scene screenshots and the edit notes are in `portfolio/`; video/audio decode and representative scene frames were checked. Public playback remains part of Gate 4.
- **Gate 4 — Public delivery: IN PROGRESS with the user's authorization.** Final release review found and removed machine-specific source paths from staged documentation. The public target is GitHub account `danhbui2009`, with a YouTube Unlisted demo and an Upwork Portfolio entry. Commit, push, video upload, and public-link verification remain to be completed and recorded here.


## Current state
- Runnable vertical slice implemented in this folder, including verified cross-period comparisons and an optional Streamlit presentation layer.
- Domain: attendance operations using a synthetic CSV fixture; no production data is connected.
- Workflow: question parsing → fixed read-only SQL → deterministic calculation → evidence reflection → answer, clarification, no-data result, or abstention. Comparisons use one bounded SELECT per period.
- LangGraph: `StateGraph` with a single bounded evidence-driven retry; exact-cap results are distinguished using one look-ahead row.
- Comparison scope: one supported metric and grouping across exactly two explicit, chronological, non-overlapping date ranges. Unequal lengths are shown; count deltas are raw totals and rate deltas are percentage points. An empty whole period withholds the comparison.
- UI phases 2.1–2.5: six examples, session-state result, safe Evidence Panel, native single/comparison rate/count charts, collapsed workflow path, and visual/accessibility polish are implemented. The light theme and narrow-width layout keep labels readable; exact results precede charts, and a visible evidence snapshot summarizes source/query ID, status, rows, and retries. Comparison charts label both date ranges and place changes below the bars. The workflow path remains derived from terminal state and is shown as an ordered text list. The Phase 2.6 local portfolio video is now recorded; publication remains pending.
- Controlled abstention demo: `demo/abstain_demo.py` adapts the conflicting duplicate-row test fixture and exits nonzero unless the workflow abstains.
- LLM provider/API: not used in this MVP; intent parsing is deterministic so the workflow runs without credentials.
- Runtime discovered: Python 3.11.9 and 3.13.11; dependency isolation uses Python 3.11.
- Existing Wise Eye source schema: not identified. Portfolio materials support ETL context only, so schema and business rules remain demo assumptions.

## Prior Phase 2.5 verification
- Primary Phase 2.5 run passed all 88 tests in 16.32s; the focused UI run passed 40 tests in 11.65s. Independent tester rerun passed all 88 in 15.43s. Python compilation, dependency health, the controlled abstention demo, and local Streamlit health (HTTP 200) passed. Visual inspection at normal, 390 px, and 320 px widths confirmed readable scope/evidence labels and a sequential comparison chart/delta table. Exact results are in `TEST_REPORT.md`.
- Independent review found no blocking issue after responsive inspection confirmed Streamlit stacks the native columns at narrow widths. Existing safe chart and workflow-path boundaries remain covered by the regression suite.

## Known product limits
- No LLM-backed natural-language parser, real database connector, persistent checkpoints, or policy retrieval. The optional UI is a local synthetic-data demo.
- The rule parser accepts a constrained English/Vietnamese question set, one explicit ISO date range for a single-period request, or two explicit ranges for a comparison. Compound metrics/groupings and invalid comparison windows ask for clarification.
- `TEST_REPORT.md` records the latest actual checks and CLI results.
