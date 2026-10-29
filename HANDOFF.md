# Deliverable 2 Laptop Handoff

Date: October 28, 2026  
Repository state reviewed: `bbd0eb4` on `main`

## Goal

Finish and verify Deliverable 2 using live Databricks access. The report needs at least five fully written pages, a one-fact/four-dimension star schema, APA research, real data-loading evidence, tutorial progress, and initial AI Verification Log entries.

## Current project evidence

- Databricks schemas and starter tables are defined in `notebooks/00_setup.sql`.
- Raw ingestion is defined in `notebooks/01_load_raw_data.sql`.
- Source inspection queries are in `notebooks/02_inspect_sources.sql`.
- Gold validation queries are in `notebooks/03_reporting_starters.sql`.
- Missing-input behavior is demonstrated in `notebooks/04_test_missing_inputs.py`.
- A synthetic keyword-ranking preview is in `notebooks/05_keyword_demo.py`.
- `docs/source-manifest.json` records these repository claims:
  - 9,544 resume rows
  - 1,048 LinkedIn job rows
  - 10,000 recruitment rows
- `README.md` and `docs/DATABRICKS-START-HERE.md` define scope, limits, role handoffs, and remaining work.

These counts and setup statements came from repository files. They have not yet been rechecked through live Databricks access in this handoff.

## Current report

The latest report created in the prior Codex session is named:

`Deliverable_2_Default_Assignment_Format.docx`

It uses the same plain assignment style as the provided ByteBites and Airbyte examples: Calibri, black text, one-inch margins, simple headings, no decorative header/footer, and default-style tables. It contains the architecture discussion, star-schema diagram, APA citations, tutorial section, and AI Verification Log.

Open the same Codex chat on the laptop and download the report output from the prior turn. The report is not committed here because this repository previously stored code and documentation, not submission binaries.

## Required live Databricks verification

1. Open `Workspace > Shared > IS4030-ATS-project > notebooks`.
2. Confirm the active catalog and schemas:
   - `workspace.is4030_bronze`
   - `workspace.is4030_silver`
   - `workspace.is4030_gold`
   - `workspace.is4030_ops`
3. Verify actual row counts for all three Bronze tables.
4. Compare source-manifest values, filenames, and checksums with the live workspace.
5. Run or inspect `02_inspect_sources.sql`; record missing-value and duplicate evidence.
6. Confirm whether Silver cleaning and final sampling are complete. Do not infer completion from empty schemas or notebook source.
7. Confirm whether `fact_evaluation` contains verified results. Empty starter tables are not analysis results.
8. Run Gold integrity checks for duplicate evaluation IDs, invalid scores/ranks, and orphan keys.
9. Run the full local or Databricks test environment with requirements installed. Record the exact command and result.
10. Capture screenshots that show the notebook title, executed cell, output, and enough workspace context to establish that the result is real.

## Report updates after verification

- Replace the notebook-source-only inspection image with an executed Databricks output screenshot.
- Update row counts only if live results differ from `docs/source-manifest.json`.
- Replace planned-method wording only when corresponding work has actually run.
- Do not claim completed MiniLM scoring, fairness, hiring accuracy, name-swap findings, human-review findings, or dashboard publication without direct evidence.
- Add the instructor meeting date, participants, feedback, and resulting changes after the meeting occurs.
- Add team member names if required on the submission copy.
- Add new AI Verification Log entries for the laptop session, including what AI did and how a team member checked it.

## Architecture constraints to preserve

- Fact grain: one resume-job-model-test-condition evaluation in one frozen study run.
- Central table: `fact_evaluation`.
- Dimensions: `dim_resume`, `dim_job`, `dim_model`, and `dim_test_condition`.
- Human ratings and detailed audit observations remain companion tables until their separate grains are defined.
- Similarity scores are not qualification percentages or predictions of hiring success.
- Synthetic name tests are narrow consistency checks, not proof of demographic fairness.
- Raw resumes, names, tokens, credentials, and Databricks configuration files must not be committed.

## Completion check

Before submission, confirm:

- At least five fully written report pages, excluding references and screenshots if the instructor interprets the rule that way.
- Real Databricks loading or inspection screenshots.
- Star-schema diagram with one fact and at least four dimensions.
- APA in-text citations and reference list.
- Tutorial steps match the current workspace.
- AI Verification Log describes actual team activity.
- Instructor meeting is scheduled or documented.
- Final DOCX opens cleanly and all pages are visually checked in Word.

