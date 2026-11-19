"""Reproducible exploratory sample. Does not certify data as fully cleaned."""
import hashlib
import re
from collections import Counter
from ats_inputs import prepare_records
from ats_scoring import score_keyword
from ats_semantic import bound_text, score_semantic

TECH_ROLES = {'Data Analyst','Business Analyst','Software Engineer','Web Developer',
              'Machine Learning Engineer','Systems Analyst','Database Administrator',
              'Cybersecurity Analyst'}
CONTROLS = {'Nurse','Sales Representative'}
TERMS = ['SQL','Python','Power BI','Excel','Tableau','QlikSense','ETL','statistics',
         'data analysis','reporting','dashboards','C++']


def build_preview(structured, recruitment, jobs, model, *, score=True):
    pools = {'structured':[], 'recruitment':[], 'control':[]}
    audit=[]
    seen=set()
    for source, records, fields in [
        ('structured',structured,['skills','positions','responsibilities','degree_names','major_field_of_studies']),
        ('recruitment',recruitment,['resume'])]:
        for row in records:
            if source=='recruitment' and row['role'] not in TECH_ROLES | CONTROLS:
                continue
            raw='|'.join(str(row.get(f,'')) for f in fields)
            rid=source+'-'+hashlib.sha256(raw.encode()).hexdigest()[:20]
            prepared, records_audit = prepare_records([dict(row,resume_id=rid)],'resume_id',fields,missing_policy='skip_missing')
            audit.extend(dict(a,source=source) for a in records_audit)
            if not prepared:
                continue
            text=prepared[0]['text']
            if source=='recruitment' and row.get('applicant_name'):
                text=re.sub(r'(?i)(?<!\w)'+re.escape(row['applicant_name'].strip())+r'(?!\w)', ' ', text)
            text=re.sub(r'https?://\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '', text)
            text=re.sub(r'(?<!\w)\+?\d[\d(). -]{7,}\d(?!\w)', ' ', text)
            text, truncated=bound_text(text,model)
            fingerprint=' '.join(text.casefold().split())
            if fingerprint in seen:
                audit.append(dict(record_id=rid,source=source,action='duplicate',reason='identical_model_input'))
                continue
            seen.add(fingerprint)
            pool='control' if source=='recruitment' and row['role'] in CONTROLS else source
            pools[pool].append(dict(resume_id=rid,text=text,source_dataset=source,
                domain_group='control' if pool=='control' else 'tech_data_proxy',
                text_truncated=truncated))
    resumes=[]
    for pool,count in [('structured',105),('recruitment',105),('control',90)]:
        candidates=sorted(pools[pool],key=lambda r:r['resume_id'])
        if len(candidates)<count:
            raise ValueError(f'Insufficient unique usable {pool} records: {len(candidates)} < {count}')
        resumes.extend(candidates[:count])
    selected_jobs=[]
    for row in jobs:
        # Prefer qualifications over introductory/company boilerplate.
        parts=re.split(r'(?i)(?:job qualifications|required skills\s*&?\s*qualifications)\s*',row['description'],maxsplit=1)
        text=parts[-1]
        text=re.split(r'(?i)\b(?:benefits|equal opportunity|note:|show more)\b',text,maxsplit=1)[0]
        jid='job-'+hashlib.sha256(row['description'].encode()).hexdigest()[:20]
        prepared,ja=prepare_records([dict(job_id=jid,text=text)],'job_id',['text'],missing_policy='skip_missing')
        audit.extend(dict(a,source='jobs') for a in ja)
        if not prepared:
            continue
        text,truncated=bound_text(text.strip(),model)
        if any(j['text']==text for j in selected_jobs):
            continue
        selected_jobs.append(dict(job_id=jid,source_id=row.get('source_id', ''),text=text,
                                  title=row['title'],company=row['company'],text_truncated=truncated))
        if len(selected_jobs)==2:
            break
    if len(selected_jobs)!=2:
        raise ValueError('Two usable jobs required.')
    results=(score_keyword(resumes,selected_jobs)+score_semantic(resumes,selected_jobs,model=model)) if score else []
    rm={r['resume_id']:r for r in resumes}; jm={j['job_id']:j for j in selected_jobs}
    for row in results:
        r,j=rm[row['resume_id']],jm[row['job_id']]
        row.update(job_title=j['title'],company=j['company'],source_dataset=r['source_dataset'],
                   domain_group=r['domain_group'],input_status='provisional_skip_missing',
                   matched_terms=', '.join(t for t in TERMS if re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',r['text'],re.I) and re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',j['text'],re.I)))
    quality=[dict(source=s,action=a,records=n) for (s,a),n in Counter((r['source'],r['action']) for r in audit).items()]
    quality += [dict(source='selected_resumes',action='text_truncated',records=sum(r['text_truncated'] for r in resumes)),
                dict(source='selected_jobs',action='text_truncated',records=sum(j['text_truncated'] for j in selected_jobs))]
    return resumes,selected_jobs,results,quality
