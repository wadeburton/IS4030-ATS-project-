"""Paired robustness audits: synthetic name swaps and keyword stuffing.

Each audit changes one thing about a resume, rescores it with the scorer held
fixed, and compares it with the same resume unchanged. Results describe this
sample and these two methods only; a name test is not a discrimination finding.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Synthetic names only. No person in the study data carries them.
NAMES = ('Emily Walsh', 'Greg Baker', 'Lakisha Washington', 'Jamal Robinson', 'Maria Hernandez', 'Wei Chen')
REFERENCE_NAME, *SWAP_NAMES = NAMES


def with_name(resumes, name=REFERENCE_NAME):
    """The comparison pool: every resume carries the same reference name line."""
    return [dict(row, text=f"name: {name}\n{row['text']}") for row in resumes]


def name_variants(resumes):
    """Each unnamed resume with the reference name swapped for each other name."""
    return [(row['resume_id'], name, f"name: {name}\n{row['text']}") for row in resumes for name in SWAP_NAMES]


def stuffing_terms(job_text, resume_texts, n=12):
    """The posting's n most distinctive single words: what a keyword stuffer would copy."""
    vectorizer = TfidfVectorizer(token_pattern=r'(?u)[\w.]+(?:\+\+|#)?').fit(list(resume_texts) + [job_text])
    weights = vectorizer.transform([job_text]).toarray()[0]
    terms = vectorizer.get_feature_names_out()
    return [terms[i] for i in sorted(range(len(terms)), key=lambda i: (-weights[i], terms[i]))[:n] if weights[i] > 0]


def stuffed_variants(resumes, terms):
    return [(row['resume_id'], 'stuffed', f"{row['text']}\nskills: {', '.join(terms)}") for row in resumes]


def tfidf_scorer(resume_texts, job_text):
    """Fit once on the unchanged batch (same settings as ats_scoring), then score any text."""
    vectorizer = TfidfVectorizer(token_pattern=r'(?u)[\w.]+(?:\+\+|#)?', ngram_range=(1, 2))
    vectorizer.fit(list(resume_texts) + [job_text])
    job = vectorizer.transform([job_text])
    return lambda texts: [float(s) for s in cosine_similarity(vectorizer.transform(texts), job).ravel().clip(0, 1)]


def minilm_scorer(model, job_text, cache):
    """Score with the frozen pretrained model. ``cache`` (text -> vector) is shared across jobs."""
    def embed(texts):
        missing = sorted({text for text in texts if text not in cache})
        if missing:
            vectors = model.encode(missing, normalize_embeddings=True, show_progress_bar=False, batch_size=64)
            cache.update(zip(missing, vectors))
        return [cache[text] for text in texts]
    job = embed([job_text])[0]
    return lambda texts: [min(1.0, max(0.0, float(vector @ job))) for vector in embed(texts)]


def with_headroom(text, model, *, max_chars=800, reserve_tokens=64):
    """Shorten a resume so added test text is never cut off by the model's limits."""
    ids = model.tokenizer(text[:max_chars].strip(), truncation=True,
                          max_length=model.max_seq_length - reserve_tokens)['input_ids']
    return model.tokenizer.decode(ids, skip_special_tokens=True).strip()


def paired_audit(resumes, variants, score):
    """Compare each (resume_id, condition, text) variant with its unchanged resume.

    Rank is 1 + the number of *other* unchanged resumes scoring strictly higher,
    computed the same way before and after, so only the variant moves.
    """
    base = score([row['text'] for row in resumes])
    index = {row['resume_id']: i for i, row in enumerate(resumes)}
    tests = score([text for _, _, text in variants])

    def rank(i, value):
        return 1 + sum(other > value for k, other in enumerate(base) if k != i)
    return [{'resume_id': resume_id, 'test_condition': condition, 'base_score': base[index[resume_id]],
             'test_score': test, 'base_rank': rank(index[resume_id], base[index[resume_id]]),
             'test_rank': rank(index[resume_id], test)}
            for (resume_id, condition, _), test in zip(variants, tests)]
