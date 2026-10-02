# Module 2 acceptance criteria

## Product behavior
- [x] Supports 5–8 explicitly documented attendance/operations questions.
- [x] Clarifies missing date ranges and ambiguous metric definitions; comparison questions require exactly two explicit, valid periods.
- [x] Uses only approved tables/views and parameterized filters; rejects any non-read-only query.
- [x] Calculates counts, rates, and two-period comparisons deterministically, with numerator and denominator defined. Count deltas are raw totals; rate deltas are percentage points calculated from the unrounded fractions.
- [x] Requires comparison periods to be chronological and non-overlapping, labels period lengths, and withholds comparison when either whole period has no rows.
- [x] Reports a subgroup count as zero when absent within a populated period, and leaves its rate/change unavailable when its denominator is zero.
- [x] Checks date coverage, empty results, missing punches, duplicates, and query/result consistency.
- [x] Allows at most one evidence-driven re-query; then answers, asks a specific clarification, or abstains.
- [x] Data answers state period, metric definition, result, source/query identifier, and material caveats. Clarifications before query have no period/evidence to report.
- [x] Uses synthetic/anonymized data; no real employee PII or credentials in the demo.
- [x] Does not produce employment or disciplinary decisions.

## Engineering and operations
- [x] Fresh setup instructions create a runnable local environment.
- [x] Demo works with synthetic data and without production credentials.
- [x] Graph state and node/conditional edges are documented.
- [x] Error paths cover invalid filters, query rejection, empty data, and tool failure.
- [x] Tests cover deterministic metrics, SQL policy, clarification/abstention, and retry bound.
- [x] Evaluation set contains representative normal, ambiguous, empty, and edge-case questions.
- [x] README includes setup, run, sample questions, known limits, and architecture.
- [x] `TEST_REPORT.md` records commands and actual results; unrun checks remain marked unverified.

## Optional Streamlit presentation
- [x] UI calls `run_question(question)` and uses the actual structured request/result contract; it does not invoke the graph directly or recompute metrics.
- [x] Single-period and comparison results have separate renderers; percentage-point changes use `pp`.
- [x] Comparison periods show inclusive day counts; unequal-length count comparisons explain that deltas are raw totals and not normalized per day.
- [x] Answered, clarification, no-data, abstained, and unsupported states have distinct presentation paths. No-data does not claim there were zero real attendance events.
- [x] Evidence presentation uses an explicit safe-field allowlist and excludes raw attendance rows, query internals, and the full graph state.
- [x] Example-question sidebar, optional Streamlit dependency, and a reproducible abstention demo are provided.
- [x] Six example buttons fill the question widget through session-state callbacks; answers persist across ordinary reruns and are cleared when the selected example or demo scenario changes.
- [x] The normal/conflicting demo selector runs the same synthetic conflict fixture as the standalone abstention demo.
- [x] The last result stored in session state is the safe presentation view, not raw graph state or source rows.
- [x] UI behavior is covered by Streamlit AppTest when the optional UI extra is installed; actual test results are recorded in `TEST_REPORT.md`.

### Optional Streamlit charts — Phase 2.3
- [x] Normal late-rate results chart Operations at 28.6% and Sales at 37.5% from the engine result.
- [x] Comparison rate chart shows Operations 50% → 20% and Sales 50% → 33.3%.
- [x] Comparison chart displays the engine deltas −30.0 pp and −16.7 pp beside the grouped bars.
- [x] A rate with denominator zero is shown as Unavailable and is omitted from plotted bars, never converted to 0%.
- [x] Count metrics are displayed as counts and never formatted with a percent sign.
- [x] Clarification, no-data, abstained, and unsupported outcomes have no chart.
- [x] The existing 62-test baseline remains passing within the expanded 75-test suite; separate tests cover chart view-model values and edge cases.
- [x] The Streamlit renderer reads chart-ready values from the presentation view model and does not read raw records or recompute metrics.
- [x] Streamlit native charts are used without adding a charting dependency.

### Optional Streamlit workflow path — Phase 2.4
- [x] Supported results show completed parse, query, metric calculation, evidence validation, and supported outcome steps.
- [x] Clarification and unsupported parse exits show that query, calculation, and evidence validation were not run.
- [x] No-data results reflect the actual graph: query and metric calculation ran, and evidence classified the empty result; the path does not mark calculation as skipped.
- [x] Abstained results show failed evidence validation and withheld outcome; query failures show metric calculation as not applicable without exposing exception text.
- [x] A re-query step appears only when `evidence_retry_count > 0`; the path labels the actual bounded retry and final validation result.
- [x] Paths are generated from terminal state evidence and never presented as live or real-time animation.
- [x] The collapsed “How this analysis worked” section renders supported, no-data, clarification, unsupported, and abstained paths.
- [x] View-model tests cover state distinctions, retry gating, and error-detail sanitization; AppTest covers terminal-state rendering, recorded retries, query-error masking, and collapsed/non-live presentation.
- [x] The 86-test regression suite and applicable smoke checks pass; actual results are recorded in `TEST_REPORT.md`.

### Optional Streamlit visual polish — Phase 2.5
- [x] The question, result status, exact figures, chart, and evidence follow a clear reading order with a restrained high-contrast theme.
- [x] Request and evidence summaries remain readable at narrow widths; comparison chart and delta table do not depend on side-by-side columns.
- [x] A visible evidence summary reports status, source/query ID, rows read, and retry count using only safe view-model fields.
- [x] Comparison charts identify the date ranges represented by Period 1 and Period 2.
- [x] Workflow steps form an ordered text sequence with explicit state labels; controls retain visible labels and native keyboard behavior.
- [x] Single-period and comparison no-data messages accurately describe the missing evidence.
- [x] The UI continues to use engine-calculated values, omits unavailable rate bars, and hides raw rows, query text, and exception details.
- [x] Applicable UI and regression checks plus desktop/narrow visual inspection are recorded in `TEST_REPORT.md`.

## Comparison scope decision

The user approved extending Module 2 to compare the same supported metric and grouping across exactly two explicit, inclusive ISO date ranges. Period 1 must precede Period 2; ranges may not overlap. Unequal durations are allowed, displayed, and not normalized for count deltas. Rate changes use percentage points. If either whole period has no rows, the comparison is withheld. These rules are reflected in `PROJECT_BRIEF.md`, implemented, and verified in `TEST_REPORT.md`.

## Completion rule
Do not mark the project complete from a successful demo answer alone. Run the applicable checks and report any acceptance item that remains unmet.
