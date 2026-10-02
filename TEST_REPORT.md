# Module 2 test report

## Portfolio Gate 2: fresh-environment verification (2026-10-02)

A copy of the project source, fixture, UI, tests, and README was placed in `.portfolio_verify/` without the existing `.venv`. The commands below ran there using a newly created Python 3.11 environment. The first pip invocation was interrupted before package installation completed; the second invocation completed successfully. This verifies a fresh virtual environment on this Windows host, not a separate clean machine or a public download.

| Check | Exact command or action | Observed result |
| --- | --- | --- |
| Create environment | `py -3.11 -m venv .venv` | **PASS**, exit 0. |
| Install from README | `.\.venv\Scripts\python.exe -m pip install -e ".[dev,ui]"` | **PASS** on completed rerun, exit 0; project, Pytest, and Streamlit installed. |
| CLI supported example | `.\.venv\Scripts\python.exe -m attendance_analyst --question "What was the late rate by department from 2026-01-05 to 2026-01-09?"` | **PASS**, exit 0; Operations 2/7 = 28.6%, Sales 3/8 = 37.5%, 18 rows, zero re-queries. |
| Full test suite | `.\.venv\Scripts\python.exe -m pytest` | **PASS**, 88 passed in 15.48s. |
| UI scenario checks | `.\.venv\Scripts\python.exe -m pytest tests\test_streamlit_app.py` | **PASS**, 18 passed in 11.51s; AppTest covers the examples, comparison, clarification, conflict abstention, and safe presentation. |
| Streamlit startup | `.\.venv\Scripts\python.exe -m streamlit run ui\app.py --server.headless true --server.address 127.0.0.1 --server.port 8776`; then `Invoke-WebRequest http://127.0.0.1:8776/_stcore/health` | **PASS**, server started and health endpoint returned HTTP 200. UI outcome coverage is from the separate AppTest row. |
| Standalone conflict | `.\.venv\Scripts\python.exe demo\abstain_demo.py` | **PASS**, exit 0; status abstained, 19 synthetic rows, zero re-queries, conflicting `SYN-001` detected. |
| Dependency health | `.\.venv\Scripts\python.exe -m pip check` | **PASS**, `No broken requirements found.` |

The original project `.venv` was not used for this gate. The verification copy and its tool-only Playwright installation are ignored by `.gitignore` and do not change the package dependencies.

## Portfolio Gate 3: recorded demo evidence (2026-10-02)

### User-voice replacement (2026-10-02)

- Inputs: the four user-provided M4A files numbered 6, 8, 9, and 10, used in that order. Their respective container durations were 47.040, 29.632, 17.600, and 43.712 seconds; each is AAC mono at 16 kHz. Their peak levels were between −1.8 and −0.8 dB.
- Output: `portfolio/demo_walkthrough_user_voice.mp4`, H.264 1440 × 900 at 25 fps plus AAC mono at 48 kHz. The 2:17.46 container has 3,434 decoded video frames reaching 2:17.36 and an audio stream reaching 2:17.47. Full decode reported no errors; output audio mean volume was −21.4 dB and peak −0.7 dB.
- The original silent footage was split into four scenes. Static waiting footage was removed between scenes; the supported-result and abstention frames were held to fit the longer voice segments. Representative frames at 0:46, 0:48, 1:16, 1:18, 1:34, 1:36, 2:08, and 2:16 were inspected for scene order and visible results. The narration was not sped up or cut. See `portfolio/VIDEO_SCRIPT.md` for the edit map.
- The original system-voice recording is retained locally for comparison. README now links to the user-voice MP4. No upload or public playback check was performed.

### Original local recording (before the voice replacement)

The local Streamlit server from Gate 2 was operated in headless Chrome with Playwright. One continuous browser recording shows the supported late-rate answer, two-period comparison, missing-period clarification, and conflict-fixture abstention. The actual UI status text was awaited before each scene; the abstention scene used the application's **Conflicting evidence** mode and the same synthetic fixture as `demo/abstain_demo.py`.

- **Recorded artifact:** `portfolio/demo_walkthrough.webm`, VP8 video, 1440 × 900, 25 fps, 2:10.72.
- **Narrated artifact:** `portfolio/demo_walkthrough_narrated.webm`, same VP8 footage with locally generated English Opus narration. The narration text and approximate scene timing are in `portfolio/VIDEO_SCRIPT.md`.
- **Visual checks:** sampled frames at 0:22, 0:55, 1:32, and 2:03. They show the supported 28.6%/37.5% result, 50.0%→20.0% and 50.0%→33.3% comparison, the transition into the conflict mode, and the abstained evidence/path view. Separate screenshots capture each final outcome.
- **Media integrity:** FFmpeg identified a 2:10.72 VP8 video stream and an Opus audio stream in the narrated file. Full decode to a null sink produced no errors. Audio volume scan reported mean −21.8 dB and peak −2.5 dB.
- **Limit:** The recording and local README link are verified on this host. Public video access has not been checked.

Previous Phase 2.5 primary verification: 2026-10-01, project-local Python 3.11 virtual environment with optional UI dependencies installed. That phase added visual and accessibility improvements; the suite had 88 tests.

## Automated checks

| Check | Command | Primary result | Independent tester result |
| --- | --- | --- | --- |
| Unit, graph, SQL-safety, evaluation, presentation, demo, and UI suite | `.\.venv\Scripts\python.exe -m pytest -o addopts= -q` | **PASS** — 88 passed in 16.32s. | **PASS** — 88 passed in 15.43s. |
| Focused presentation and Streamlit UI suite | `.\.venv\Scripts\python.exe -m pytest -o addopts= -q tests\test_ui_presentation.py tests\test_streamlit_app.py` | **PASS** — 40 passed in 11.65s. | Included in the 88-test full suite; no separate focused rerun. |
| Python compile | `.\.venv\Scripts\python.exe -m compileall -q src ui demo tests` | **PASS** — exit code 0, no diagnostics. | **PASS** — exit code 0, no diagnostics. |
| Dependency health | `.\.venv\Scripts\python.exe -m pip check` | **PASS** — `No broken requirements found.` | **PASS** — `No broken requirements found.` |
| Controlled abstention demo | `.\.venv\Scripts\python.exe demo\abstain_demo.py` | **PASS** — exit code 0; status `abstained`; 19 rows; zero re-queries; conflicting `SYN-001` detected and result withheld. | **PASS** — same expected outcome; exit code 0. |
| Streamlit server health | `(Invoke-WebRequest -Uri 'http://127.0.0.1:8775/_stcore/health' -TimeoutSec 5).StatusCode` | **PASS** — HTTP 200 on the local server. | **PASS** — HTTP 200, body `ok`. |

## Phase 2.1, 2.2, and 2.3 coverage

- All six example buttons fill the keyed question widget and then reach their expected statuses: four answered examples, one no-data example, and one clarification example.
- The conflicting-evidence scenario uses the same fixture helper as the standalone abstention demo and reaches `abstained` without exposing the source row ID in the stored view model.
- The safe result persists when the question widget causes a rerun; selecting another example clears it. Changing the demo scenario also clears the result.
- Rate comparisons display the one-day/four-day period labels and −30.0 pp / −16.7 pp changes. Count comparisons show the unequal-length raw-total caveat.
- Clarification records zero SELECT statements. No-data language says the empty fixture result does not establish that no real attendance event occurred.
- The session-state result is `to_safe_view(raw_result)`, excluding source rows, query text/parameters, and the full graph state. Evidence ID comes from the structured `query_id` field. Issues map to fixed safe messages.
- Single-period rate chart view model uses the engine values Operations 28.6% and Sales 37.5%; Streamlit renders it with native st.bar_chart.
- Comparison rate chart uses engine values Operations 50.0% → 20.0% (−30.0 pp) and Sales 50.0% → 33.3% (−16.7 pp); the delta table now follows the grouped bars.
- Count charts use engine count and count_delta values, with no percent formatting.
- A rate denominator of zero maps to a null plotted value and Unavailable; the renderer omits it from bars rather than plotting it as 0%.
- New view-model tests cover single/comparison rate/count, status/final-status gating, denominator zero, and raw-row isolation. AppTest checks example flows using actual results.
- No charting library was added. Local Streamlit 1.64.0 native st.bar_chart supports grouped series with stack=False.

## Phase 2.4 workflow path coverage

- The safe `workflow_path` is derived from terminal graph state. Supported, clarification, unsupported, no-data, abstained, query-error, and one-retry paths reflect the graph's actual execution. No-data records that metric calculation ran on the empty result; parse exits mark query, calculation, and evidence as not run.
- A retry step appears only for `evidence_retry_count == 1`; the view model checks query passes equal retry count plus one and keeps the retry bounded.
- Query exceptions are represented only as a generic failed query. Metric calculation is marked not applicable, and raw driver/error text is absent from the workflow path and safe view.
- Streamlit renders the completed path as an ordered text list inside a collapsed “How this analysis worked” expander and states that it is not a live trace.
- AppTest covers terminal statuses, collapsed/non-live rendering, a recorded retry step, and query-error detail isolation. View-model tests cover state mapping, no-data calculation, retry gating, and error sanitization.

## Phase 2.5 visual and accessibility coverage

- The light Streamlit theme uses dark text on a pale background and a teal primary control. Calculated color-pair contrast ratios are 13.24:1 for body text/background and 6.00:1 for white/primary.
- The result status and exact figures appear before the chart. A visible evidence snapshot shows status, rows read, evidence ID, source, and retry count using the safe view model.
- The comparison chart labels both date ranges; the delta table follows the bars. A comparison with an empty period states that at least one period lacks rows and withholds the result.
- Native text labels and controls remain available to keyboard and accessibility APIs. Browser accessibility output exposed the workflow as a numbered list with explicit text states and labeled question/scenario controls. Pressing Tab from the question text area focused the Analyze button.
- The running app was inspected at the default browser size and explicit 390 px and 320 px widths. At 320 px, the scope fields and evidence summary stacked vertically with full metric and date labels; chart and delta table remained sequential. The detailed comparison dataframe still scrolls horizontally at this width.
- AppTest verifies result-before-chart order, visible evidence summary, comparison date labels, comparison no-data copy, and ordered workflow text.

## Previous CLI smoke check (Phase 2.3)

| Case | Command and observed result |
| --- | --- |
| Single-period late rate | `.\.venv\Scripts\python.exe -m attendance_analyst --question "What was the late rate by department from 2026-01-05 to 2026-01-09?"` — **PASS**, exit 0. Operations: 2/7 = 28.6%; Sales: 3/8 = 37.5%; one read-only SELECT over 18 synthetic rows; zero retries. |

## Independent review and tester

Independent Phase 2.3 code review confirmed that charts consume safe view-model values copied from engine output, non-answered and non-supported outcomes are gated out, denominator-zero rates are unavailable, count units stay counts, and raw rows do not reach the chart renderer. Explicit supported-status gating and regression coverage are in place.

For Phase 2.4, independent review confirmed that displayed steps match graph execution, no-data calculation is represented correctly, and raw query errors do not leak. Following the reviewer's request, AppTest coverage was added for retry rendering and query-error masking. The independent tester reran the final 86-test suite (12.11s), compilation, dependency check, abstention demo, and both new focused AppTests. Prior independent UI smoke checks also confirmed all terminal paths, the collapsed/non-live expander, and headless health (HTTP 200 `ok`). No files were changed by the reviewer or tester.

For Phase 2.5, the independent reviewer found no blocking correctness, accessibility, or security issue after the 320 px and 390 px responsive inspection resolved an initial concern about two-column summaries. The independent tester passed the 88-test suite in 15.43s, compilation, dependency check, abstention demo, and Streamlit health (HTTP 200 `ok`). Neither reviewer nor tester edited files.

## Remaining limits

No production connector, external database schema, or real attendance policy was tested. The UI and conflict scenario use synthetic data only. The detailed comparison dataframe scrolls horizontally on a 320 px viewport; the separate delta table supplies the key period values and change. A local Phase 2.6 video was recorded and verified as described above. No deployment or publication was performed.
