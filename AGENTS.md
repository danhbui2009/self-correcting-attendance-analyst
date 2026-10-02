# Module 2 project instructions

## Objective
Build a portfolio-ready, runnable **Evidence-Checking Operations Analyst** for attendance data. It should accept a business question, query approved data, calculate results, check whether the evidence supports its draft, and ask for clarification or report a limitation when the evidence is insufficient.

## Scope and source of truth
- This folder is the write boundary for Module 2. Do not edit unrelated folders or the existing Wise Eye source project without an explicit request.
- First inspect the files and runtime actually present. Do not assume a database schema, credential, model provider, or existing implementation.
- Use synthetic or anonymized attendance data for development and demos. Do not copy employee PII, secrets, or production data into this project.
- Keep Module 2 focused on a single analyst workflow. Module 3 RAG, policy search, and multi-agent product behavior are out of scope.

## Automatic execution workflow
For a request to run or implement Module 2:
1. Read `PROJECT_BRIEF.md`, `WORKFLOW.md`, `ACCEPTANCE.md`, and `STATUS.md`.
2. Inspect the current project, identify what exists, and report only material assumptions or missing inputs.
3. Create or update a short plan with files, milestones, and acceptance checks. Continue without pausing for routine implementation choices.
4. If subagents are available, delegate independent, read-only discovery or review tasks with precise outputs. Keep one implementation owner for shared files. Do not claim a subagent completed work until its result is received.
5. Implement the smallest complete vertical slice that satisfies acceptance criteria. Prefer deterministic calculations and typed inputs/outputs. Generated SQL must be restricted to approved read-only tables/views and validated before execution.
6. Run the relevant tests and evaluation cases. Record commands and observed results in `TEST_REPORT.md`. If a check fails, fix the cause and rerun the affected checks.
7. Update `STATUS.md` and deliver a concise handoff with changed files, run instructions, checks/results, limitations, and next steps.

## Evidence and retry rules
- Treat reflection as a bounded evidence check, not self-training or unconstrained chain-of-thought.
- Check date coverage, row counts, denominators, missing values, query/result consistency, and whether each claim is supported by returned data.
- Permit at most one evidence-driven re-query for the same user request. If evidence remains incomplete, ask a specific clarification or abstain with the reason.
- Include the reporting period, metric definition, evidence source/query identifier, and data caveats in answers.
- Never invent a metric, row, source, or test result.

## Safety and boundaries
- Database access must be read-only. No generated `INSERT`, `UPDATE`, `DELETE`, DDL, or external side effects.
- Do not make disciplinary, eligibility, or other employment decisions. Escalate sensitive or ambiguous cases to a human.
- Do not publish, deploy, contact external services, or commit/push unless the user explicitly requests that action.
- Do not modify files outside this project folder unless the user explicitly authorizes the expanded scope.

## When complete
A task is complete only when the applicable acceptance checks have been run and reported, or when a concrete external blocker is documented. Separate verified results from assumptions and remaining work.
