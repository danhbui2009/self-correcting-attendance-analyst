# Module 2 — Self-Correcting AI Data Analyst

## Portfolio purpose
Build the second step in the user's AI/business-operations portfolio series. Module 1 demonstrates a stateful workflow; Module 2 demonstrates a data analyst that uses SQL/Python tools and performs a bounded evidence check before answering. Module 3 will later add policy RAG and broader BI routing.

## Business domain
Use workforce attendance and operations as the first case, aligned with the user's Wise Eye / HR operations context. Keep the design adaptable to sales or inventory data later, without implementing those domains now.

## User story
A manager asks a question such as: “How did late arrivals change by department last month?” The analyst checks that the period and metric are defined, runs a read-only query on an approved dataset, calculates the metric, verifies coverage and consistency, then returns a concise answer with its period, definition, evidence, and caveats. It asks a targeted question or abstains when required evidence is missing.

## Data contract (initial proposal; validate against actual inputs)
Use pseudonymous/synthetic fields only:
- `employee_key`: non-identifying synthetic key
- `work_date`
- `department`
- `scheduled_start`, `scheduled_end`
- `actual_check_in`, `actual_check_out`
- `attendance_status`
- `exception_type`
- `source_row_id`

Do not treat this proposed schema as an existing Wise Eye schema. Add only fields required by accepted questions. Document timezone, overnight shift, duplicate, missing-punch, and denominator rules.

## Supported question set
The initial MVP implements seven query forms, each using one explicit inclusive ISO date range:
1. Late-arrival count overall or grouped by department, shift, week, or day.
2. Late-arrival rate overall or grouped by department, shift, week, or day.
3. Missing check-in count or rate, optionally grouped by department, shift, week, or day.
4. Missing check-out count or rate, optionally grouped by department, shift, week, or day.
5. Attendance exception counts grouped by `exception_type`.
6. Attendance row counts grouped by attendance status.
7. Attendance row counts grouped by department, shift, week, or day.

The accepted scope also includes comparing any one supported metric across exactly two explicit inclusive ISO date ranges. Both periods use the same metric and grouping. Period 1 must precede Period 2 and the ranges cannot overlap. Unequal period lengths are allowed and displayed. Count comparisons report raw total differences without normalizing for period length; rate comparisons report percentage-point changes. If either period returns no rows, withhold the comparison instead of treating that period as zero. A subgroup absent within a populated period has a zero count; its rate and rate change are unavailable when the denominator is zero.

Do not support employee-level ranking or recommendations about employment action in the MVP.

## Expected deliverables
- Runnable local demo and documented setup/run commands.
- Read-only data/query boundary and deterministic metric calculations.
- LangGraph stateful workflow with bounded validation/re-query and clarification/abstention paths.
- Synthetic sample data and a small evaluation set.
- Tests for core calculations, query safety, and important edge cases.
- README, architecture/workflow description, and `TEST_REPORT.md`.
- An evaluation set covering supported intents, two-period comparisons, clarification, empty periods, and out-of-scope employment decisions.

## MVP stack and provider boundary
Python 3.11+; LangGraph `StateGraph`; SQLite in memory loaded from the synthetic CSV; typed graph state; pytest; command-line demo. The MVP uses a deterministic intent parser and makes no LLM/API calls, so the sample can run without credentials. This is an intentional first runnable slice; an LLM-backed parser is a later extension and must retain the same validated request schema, read-only query boundary, and offline test path.

## Verified source material and assumptions
The inspected Wise Eye portfolio slides describe an Access MDB ETL and mention date/time normalization, missing/invalid fields, deduplication, and `Log_Key`. They do not establish the actual attendance schema or metric definitions. The workforce dashboard material identifies Department, Shift, and Date dimensions and labels its sample data synthetic. Therefore the local schema, departments, shift times, exception labels, 5-minute grace period, and metric denominators in this MVP are explicit demo assumptions, not verified Wise Eye business rules.
