"""Provisional keyword scoring for one frozen study run, not hiring decisions."""
import json
from uuid import NAMESPACE_URL, uuid5

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ats_inputs import prepare_records


def score_keyword(resumes, jobs, *, test_condition_id='normal'):
    """Score prepared ID/text records; return star-schema-ready dictionaries.

    Fit once on this batch of resumes and jobs. Scores from separately fitted
    batches are not comparable. Rank unrounded scores; break ties by resume ID.
    Missing-value decisions belong in prepare_records before this function.
    """
    if not isinstance(test_condition_id, str) or not test_condition_id.strip():
        raise ValueError('A test condition ID is required.')
    resumes = list(resumes)
    jobs = list(jobs)
    for rows, key in ((resumes, 'resume_id'), (jobs, 'job_id')):
        if not rows:
            raise ValueError('At least one resume and job are required.')
        if any(not isinstance(row.get('text'), str) for row in rows):
            raise ValueError('Prepared text must be a string.')
        prepare_records(rows, key, ['text'])
        if any(row[key] != row[key].strip() for row in rows):
            raise ValueError('IDs must have no surrounding whitespace.')
    resumes = sorted(resumes, key=lambda row: row['resume_id'])
    jobs = sorted(jobs, key=lambda row: row['job_id'])
    # Preserve technical tokens such as C++, C#, and .NET; bigrams include Power BI.
    vectorizer = TfidfVectorizer(token_pattern=r'(?u)[\w.]+(?:\+\+|#)?',
                                 ngram_range=(1, 2))
    vectors = vectorizer.fit_transform([row['text'] for row in resumes + jobs])
    scores = cosine_similarity(vectors[:len(resumes)], vectors[len(resumes):])
    output = []
    for j, job in enumerate(jobs):
        order = sorted(range(len(resumes)), key=lambda i: (-scores[i, j], resumes[i]['resume_id']))
        for rank, i in enumerate(order, 1):
            resume_id = resumes[i]['resume_id']
            identity = [resume_id, job['job_id'], 'tfidf', test_condition_id]
            output.append({'evaluation_id': str(uuid5(NAMESPACE_URL, json.dumps(identity))),
                           'resume_id': resume_id, 'job_id': job['job_id'],
                           'model_name': 'tfidf',
                           'similarity_score': round(float(scores[i, j].clip(0, 1)), 3),
                           'rank_position': rank, 'test_condition_id': test_condition_id})
    return output
