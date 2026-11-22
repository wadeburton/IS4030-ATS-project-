# Scope change: target job postings expanded from 2–3 to 20

*Draft text for the Business Problem & Scope section. Edit into the report's voice.*

Deliverable 1 scoped the study to two to three target job postings. During dashboard
development we expanded this to 20 postings, all drawn from the same job family (Data
Analyst / Business Intelligence) and the same source (the LinkedIn Data Jobs dataset already
loaded in our Bronze layer). The resume sample is unchanged: 300 resumes, 70% tech/data and
30% out-of-domain controls.

**Why we expanded.** With only two or three postings, any pattern we observed could have been
a property of those particular postings rather than of the scoring methods. The full set
confirmed that concern. Across the 20 postings, agreement between the keyword and semantic
rankings (Spearman rank correlation over all 300 resumes) ranged from -0.32 to 0.59 with a
median of 0.12, and 14 of the 20 postings fell below 0.3. The two methods' top-20 lists shared
between 0 and 14 candidates (8 on average). The first three postings alone had also suggested
that neither method ever ranked an out-of-domain control resume in its top 20; over 20
postings that did not hold. TF-IDF placed control resumes in 20 of its 400 top-20 slots
(across 3 postings) and MiniLM in 3 of 400 (1 posting). Conclusions drawn from three postings
would have overstated how well both methods separate relevant from irrelevant resumes.

**How the added postings were selected.** We did not hand-pick them. The 17 additional
postings were taken, in order, from the same deterministic query used for the original
sample (title matches "data analyst" or "business intelligence", description longer than 150
characters, ordered by a hash of the description) and passed through the same preparation
steps: qualifications extracted from boilerplate, text bounded to the MiniLM token limit and
to 1,000 characters, and exact duplicates removed.

**What changed in the system.** The pipeline's `study_job_count` quality gate, which blocks
scoring when the job table is outside the agreed range, was widened from 2–3 to 2–20. The
gate still exists and still blocks a table of 21 or more postings. `dim_job` now holds 20
rows and `fact_evaluation` holds 12,000 rows: one per resume, posting, and model (300 × 20 × 2), with zero
duplicate, invalid, or orphaned rows.

**What did not change.** One job family, the 300-resume sample and its 70/30 composition, the
two scoring methods, the star schema, and the limits on interpretation: scores measure text
similarity within this sample, not candidate quality.

**Limitation introduced.** The planned human review of 30–50 resume/job pairs now covers a
smaller share of all scored pairs than it would have with three postings. Reviewed pairs
should be sampled across several postings rather than concentrated in one.
