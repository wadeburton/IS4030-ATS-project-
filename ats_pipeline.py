"""Small gated run path for the ATS scoring prototype."""
from datetime import datetime, timezone
from uuid import uuid4

from ats_inputs import prepare_records
from ats_scoring import score_keyword


def _check(name, status, *, severity='blocking', input_count=0, fail_count=0, detail=''):
    return {'check_name': name, 'status': status, 'severity': severity,
            'input_count': input_count, 'fail_count': fail_count, 'detail': detail}


def _prepare(rows, key, *, missing_policy, max_chars):
    rows = list(rows)
    try:
        clean, audit = prepare_records(rows, key, ['text'], missing_policy=missing_policy)
    except ValueError as exc:
        message = str(exc).casefold()
        name = 'unique_identifiers' if 'duplicate' in message else 'valid_required_inputs'
        return [], [], [_check(name, 'failed', input_count=len(rows), fail_count=1,
                               detail='Input contains a duplicate ID or invalid/missing required value.')]
    if not clean:
        return [], audit, [_check('usable_records', 'failed', input_count=len(rows),
                                  fail_count=len(rows), detail='No rows have usable qualification text.')]
    for row in clean:
        row['text'] = row['text'].removeprefix('text: ')
    too_long = [row for row in clean if len(row['text']) > max_chars]
    checks = [_check('valid_required_inputs', 'passed', input_count=len(rows)),
              _check('unique_identifiers', 'passed', input_count=len(clean)),
              _check('text_character_limit', 'failed' if too_long else 'passed',
                     input_count=len(clean), fail_count=len(too_long),
                     detail=f'Text must be at most {max_chars} characters.'),
              _check('usable_records', 'passed', input_count=len(clean))]
    skipped = sum(row['action'] == 'skipped' for row in audit)
    partial = sum(row['action'] == 'kept_partial' for row in audit)
    if skipped or partial:
        checks.append(_check('missing_text_audit', 'warning', severity='warning',
                             input_count=len(rows), fail_count=skipped + partial,
                             detail=f'{skipped} skipped and {partial} kept with partial text; see counts.'))
    fingerprints = [row['text'].casefold() for row in clean]
    duplicate_count = len(fingerprints) - len(set(fingerprints))
    if duplicate_count:
        checks.append(_check('duplicate_prepared_text', 'warning', severity='warning',
                             input_count=len(clean), fail_count=duplicate_count,
                             detail='Exact repeated text needs review before the study sample is frozen.'))
    return clean, audit, checks


def _status(checks):
    if any(c['severity'] == 'blocking' and c['status'] == 'failed' for c in checks):
        return 'failed'
    if any(c['status'] == 'warning' for c in checks):
        return 'warning'
    return 'passed'


def _score_checks(scores, resume_count, job_id, model_name):
    checks = []
    wrong_jobs = sum(row.get('job_id') != job_id for row in scores)
    wrong_models = sum(row.get('model_name') not in ({'tfidf', 'minilm'} if model_name == 'both' else {model_name}) for row in scores)
    invalid_scores = sum(not isinstance(row.get('similarity_score'), (int, float))
                         or not 0 <= row['similarity_score'] <= 1 for row in scores)
    invalid_ranks = sum(not isinstance(row.get('rank_position'), int) or row['rank_position'] < 1 for row in scores)
    duplicate_ids = len(scores) - len({row.get('evaluation_id') for row in scores})
    for name, count, detail in [
        ('selected_job_only', wrong_jobs, 'Scores must belong to the selected job.'),
        ('selected_model_only', wrong_models, 'Scores must belong to the selected model selection.'),
        ('scores_between_zero_and_one', invalid_scores, 'Similarity scores must be in [0, 1].'),
        ('positive_ranks', invalid_ranks, 'Ranks must be positive integers.'),
        ('unique_evaluation_ids', duplicate_ids, 'Evaluation IDs must be unique within a run.'),
        ('expected_score_count', max(0, len(scores) - resume_count * (2 if model_name == 'both' else 1)),
         'Unexpected excess score rows.')]:
        checks.append(_check(name, 'failed' if count else 'passed', input_count=len(scores),
                             fail_count=count, detail=detail))
    expected = resume_count * (2 if model_name == 'both' else 1)
    checks.append(_check('complete_score_count', 'failed' if len(scores) != expected else 'passed',
                         input_count=len(scores), fail_count=abs(expected - len(scores)),
                         detail=f'Expected {expected} scores for the selected job/model run.'))
    return checks


def run_ats(resumes, jobs, *, job_id, model_name='tfidf', missing_policy='skip_missing',
            run_id=None, semantic_model=None, max_chars=1000, study_mode=False):
    """Validate, gate, score one selected job, and return dashboard-ready records.

    ``scores`` retains the seven required fact fields and adds ``run_id`` for
    operational traceability. Strip ``run_id`` when loading the frozen fact table.
    """
    run_id = run_id or str(uuid4())
    started = datetime.now(timezone.utc).isoformat()
    if model_name not in {'tfidf', 'minilm', 'both'}:
        raise ValueError("model_name must be 'tfidf', 'minilm', or 'both'.")
    resumes = list(resumes)
    jobs = list(jobs)
    selected = [job for job in jobs if job.get('job_id') == job_id]
    checks = []
    clean_resumes, resume_audit, resume_checks = _prepare(
        resumes, 'resume_id', missing_policy=missing_policy, max_chars=max_chars)
    clean_jobs, job_audit, job_checks = _prepare(
        jobs, 'job_id', missing_policy=missing_policy, max_chars=max_chars)
    checks.extend(resume_checks)
    checks.extend(job_checks)
    if len(selected) != 1:
        checks.append(_check('selected_job_exists_once', 'failed', input_count=len(jobs), fail_count=1,
                             detail='The selected job ID must occur exactly once.'))
    else:
        checks.append(_check('selected_job_exists_once', 'passed', input_count=1))
    if study_mode:
        if not 300 <= len(clean_resumes) <= 500:
            checks.append(_check('study_resume_count', 'failed', input_count=len(clean_resumes), fail_count=1,
                                 detail='Study runs require 300–500 usable resumes.'))
        else:
            checks.append(_check('study_resume_count', 'passed', input_count=len(clean_resumes)))
        if not 2 <= len(clean_jobs) <= 3:
            checks.append(_check('study_job_count', 'failed', input_count=len(clean_jobs), fail_count=1,
                                 detail='Study runs require 2–3 usable jobs.'))
        else:
            checks.append(_check('study_job_count', 'passed', input_count=len(clean_jobs)))
        domain_labels = [row.get('domain_group') for row in resumes]
        if all(label in {'tech_data_proxy', 'control'} for label in domain_labels) and domain_labels:
            tech_share = sum(label == 'tech_data_proxy' for label in domain_labels) / len(domain_labels)
            ratio_ok = 0.70 <= tech_share <= 0.70 + 1 / len(domain_labels)
            checks.append(_check('study_domain_ratio', 'passed' if ratio_ok else 'failed',
                                 input_count=len(domain_labels), fail_count=0 if ratio_ok else 1,
                                 detail=f'Tech/data share is {tech_share:.1%}; target is 70/30.'))
        else:
            checks.append(_check('study_domain_ratio', 'failed', input_count=len(domain_labels), fail_count=1,
                                 detail='Every study resume needs a tech_data_proxy or control domain_group label.'))
    quality_status = _status(checks)
    quality = {'run_id': run_id, 'status': quality_status, 'checks': [dict(c, run_id=run_id) for c in checks],
               'resume_input_count': len(resumes), 'resume_usable_count': len(clean_resumes),
               'resume_skipped_count': sum(x['action'] == 'skipped' for x in resume_audit),
               'resume_partial_count': sum(x['action'] == 'kept_partial' for x in resume_audit),
               'job_input_count': len(jobs), 'job_usable_count': len(clean_jobs),
               'job_skipped_count': sum(x['action'] == 'skipped' for x in job_audit)}
    run = {'run_id': run_id, 'status': 'blocked' if quality_status == 'failed' else 'running',
           'job_id': job_id, 'model_name': model_name, 'quality_status': quality_status,
           'resume_count': len(clean_resumes), 'skipped_resume_count': quality['resume_skipped_count'],
           'score_count': 0, 'started_at': started, 'completed_at': None}
    if quality_status == 'failed':
        run.update(status='blocked', completed_at=datetime.now(timezone.utc).isoformat())
        return {'run': run, 'quality': quality, 'scores': []}

    resumes_for_scoring = clean_resumes
    jobs_for_scoring = [row for row in clean_jobs if row['job_id'] == job_id]
    if model_name in {'minilm', 'both'}:
        from ats_semantic import bound_text, load_model, score_semantic
        semantic_model = semantic_model or load_model()
        resumes_for_scoring = [dict(row, text=bound_text(row['text'], semantic_model)[0]) for row in clean_resumes]
        jobs_for_scoring = [dict(row, text=bound_text(row['text'], semantic_model)[0]) for row in jobs_for_scoring]
        truncated = sum(a['text'] != b['text'] for a, b in zip(clean_resumes, resumes_for_scoring))
        if truncated:
            check = _check('minilm_token_limit', 'warning', severity='warning', input_count=len(clean_resumes),
                           fail_count=truncated, detail=f'{truncated} resume texts were bounded to the model token limit.')
            check['run_id'] = run_id
            checks.append(check)
            quality['checks'].append(check)
            quality['status'] = 'warning'

    scores = []
    if model_name in {'tfidf', 'both'}:
        scores.extend(score_keyword(resumes_for_scoring, jobs_for_scoring))
    if model_name in {'minilm', 'both'}:
        scores.extend(score_semantic(resumes_for_scoring, jobs_for_scoring, model=semantic_model))
    score_checks = _score_checks(scores, len(clean_resumes), job_id, model_name)
    checks.extend(score_checks)
    quality['checks'].extend(dict(c, run_id=run_id) for c in score_checks)
    if any(c['status'] == 'failed' for c in score_checks):
        quality['status'] = 'failed'
        scores = []
        run['status'] = 'failed'
    else:
        scores = [dict(row, run_id=run_id) for row in scores]
        run['status'] = 'succeeded'
    run['score_count'] = len(scores)
    run['quality_status'] = quality['status']
    run['completed_at'] = datetime.now(timezone.utc).isoformat()
    return {'run': run, 'quality': quality, 'scores': scores}


def build_dashboard_view(run_rows, quality_rows, score_rows, *, selected_run_id):
    """Filter persisted run, quality, and score table rows for a dashboard view."""
    runs = [row for row in run_rows if row.get('run_id') == selected_run_id]
    if len(runs) != 1:
        raise ValueError('selected_run_id must match exactly one run row.')
    checks = [row for row in quality_rows if row.get('run_id') == selected_run_id]
    scores = [row for row in score_rows if row.get('run_id') == selected_run_id]
    return {'run': runs[0], 'quality_checks': checks, 'quality_status': runs[0].get('quality_status'),
            'scores': scores, 'score_count': len(scores)}
