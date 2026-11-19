"""Pretrained MiniLM scoring. Model files download; resume text stays on compute."""
import json
from uuid import NAMESPACE_URL, uuid5
from ats_inputs import prepare_records

MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'


def load_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME, device='cpu')


def bound_text(text, model):
    """Explicitly bound to 1000 characters and the real tokenizer's token limit.

    Preview uses the leading text. Record truncation and review lost content
    before the final study. Both scoring methods must receive this same text.
    """
    original = text
    text = text[:1000].strip()
    tokens = model.tokenizer(text, truncation=True, max_length=model.max_seq_length)
    text = model.tokenizer.decode(tokens['input_ids'], skip_special_tokens=True).strip()
    if not text:
        raise ValueError('No usable text after bounding.')
    return text, text != original


def score_semantic(resumes, jobs, *, model=None, test_condition_id='normal'):
    resumes, jobs = list(resumes), list(jobs)
    if not isinstance(test_condition_id,str) or not test_condition_id.strip():
        raise ValueError('A test condition ID is required.')
    for rows,key in ((resumes,'resume_id'),(jobs,'job_id')):
        if not rows or any(not isinstance(row.get('text'),str) for row in rows):
            raise ValueError('Nonempty prepared text records required.')
        prepare_records(rows,key,['text'])
        if any(row[key] != row[key].strip() for row in rows):
            raise ValueError('IDs must have no surrounding whitespace.')
    model = model if model is not None else load_model()
    resumes = sorted(resumes,key=lambda r:r['resume_id'])
    jobs = sorted(jobs,key=lambda r:r['job_id'])
    texts = [bound_text(r['text'],model)[0] for r in resumes+jobs]
    vectors = model.encode(texts,normalize_embeddings=True,show_progress_bar=False)
    scores = (vectors[:len(resumes)] @ vectors[len(resumes):].T).clip(0,1)
    result=[]
    for j,job in enumerate(jobs):
        for rank,i in enumerate(sorted(range(len(resumes)),key=lambda i:(-float(scores[i,j]),resumes[i]['resume_id'])),1):
            rid=resumes[i]['resume_id']
            identity=[rid,job['job_id'],'minilm',test_condition_id]
            result.append(dict(evaluation_id=str(uuid5(NAMESPACE_URL,json.dumps(identity))),
                resume_id=rid,job_id=job['job_id'],model_name='minilm',
                similarity_score=round(float(scores[i,j]),3),rank_position=rank,
                test_condition_id=test_condition_id))
    return result
