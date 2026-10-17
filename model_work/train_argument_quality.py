"""Train a bounded CPU pairwise-convincingness model; never an essay grade."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import random
import shutil
import time

from model_work.public_arguments import SOURCE, digest, text_hash


def group_split(rows,seed=20261017):
    topics=sorted({r['topic'] for r in rows});random.Random(seed).shuffle(topics)
    if len(topics)<5:raise ValueError('Need at least five independent debate topics.')
    n=max(1,round(len(topics)*.2))
    memberships={'test':set(topics[:n]),'validation':set(topics[n:2*n]),'train':set(topics[2*n:])}
    splits={name:[r for r in rows if r['topic'] in groups] for name,groups in memberships.items()}
    # Remove cross-split exact argument duplicates (including pair reversals).
    # Never select a topic based on its test labels or measured test performance.
    test_hashes={text_hash(r[k]) for r in splits['test'] for k in ('a1','a2')}
    before={k:len(v) for k,v in splits.items()}
    splits['validation']=[r for r in splits['validation'] if not any(text_hash(r[k]) in test_hashes for k in ('a1','a2'))]
    protected=test_hashes|{text_hash(r[k]) for r in splits['validation'] for k in ('a1','a2')}
    splits['train']=[r for r in splits['train'] if not any(text_hash(r[k]) in protected for k in ('a1','a2'))]
    if any(not rows for rows in splits.values()):raise ValueError('Leakage filtering left an empty split.')
    return splits,{k:before[k]-len(v) for k,v in splits.items()}


def metrics(y,prediction):
    from sklearn.metrics import accuracy_score,balanced_accuracy_score,f1_score
    return {'accuracy':float(accuracy_score(y,prediction)),
            'balanced_accuracy':float(balanced_accuracy_score(y,prediction)),
            'macro_f1':float(f1_score(y,prediction,average='macro',zero_division=0)), 'pairs':len(y)}


def labels(rows):
    import numpy as np
    return np.asarray([1 if r['label']=='a1' else 0 for r in rows])


def features(vectorizer,rows):
    return (vectorizer.transform([r['a1'] for r in rows])-vectorizer.transform([r['a2'] for r in rows])).tocsr()


def train(prepared,output):
    import joblib
    import numpy as np
    import sklearn
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion
    from sklearn.linear_model import LogisticRegression
    from threadpoolctl import threadpool_limits
    start=time.monotonic();prepared=Path(prepared)
    manifest=json.loads((prepared/'manifest.json').read_text())
    content=(prepared/'pairs.jsonl').read_bytes()
    if manifest.get('license')!='CC-BY-4.0' or manifest.get('commit')!=SOURCE['commit'] or digest(content)!=manifest.get('pairs_sha256'):
        raise ValueError('Only the pinned, integrity-checked, commercially eligible human corpus is supported.')
    rows=[json.loads(line) for line in content.decode().splitlines() if line.strip()]
    if len(rows)!=manifest['pair_count'] or any(r['license']!='CC-BY-4.0' or r['label'] not in ('a1','a2') for r in rows):
        raise ValueError('Invalid native annotations.')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    splits,removed=group_split(rows)
    vectorizer=FeatureUnion([
        ('words',TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=20000,sublinear_tf=True,dtype=np.float32)),
        ('characters',TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=3,max_features=30000,sublinear_tf=True,dtype=np.float32))])
    unique_texts=sorted({r[k] for r in splits['train'] for k in ('a1','a2')})
    with threadpool_limits(limits=2):
        vectorizer.fit(unique_texts)
        xtrain=features(vectorizer,splits['train']);xval=features(vectorizer,splits['validation'])
        ytrain=labels(splits['train']);yval=labels(splits['validation'])
        candidates=[];best=None
        for c in (.1,1.,10.):
            classifier=LogisticRegression(C=c,fit_intercept=False,max_iter=1000,solver='liblinear',random_state=42)
            classifier.fit(xtrain,ytrain)
            score=metrics(yval,classifier.predict(xval))
            candidates.append({'C':c,'validation':score})
            print(json.dumps({'stage':'validation','C':c,'balanced_accuracy':score['balanced_accuracy']}),flush=True)
            if best is None or score['balanced_accuracy']>best[0]:best=(score['balanced_accuracy'],c)
        # Freeze the chosen configuration before touching test labels/predictions.
        chosen=best[1]
        final_rows=splits['train']+splits['validation']
        final_texts=sorted({r[k] for r in final_rows for k in ('a1','a2')})
        vectorizer.fit(final_texts)
        xfinal=features(vectorizer,final_rows);xtest=features(vectorizer,splits['test'])
        yfinal=labels(final_rows);ytest=labels(splits['test'])
        classifier=LogisticRegression(C=chosen,fit_intercept=False,max_iter=1000,solver='liblinear',random_state=42).fit(xfinal,yfinal)
        pred=classifier.predict(xtest)
        margin=classifier.decision_function(xtest)
    majority=int(Counter(yfinal).most_common(1)[0][0])
    length_predictions=np.asarray([1 if len(r['a1'].split())>=len(r['a2'].split()) else 0 for r in splits['test']])
    per_topic={topic:metrics(ytest[[r['topic']==topic for r in splits['test']]],pred[[r['topic']==topic for r in splits['test']]]) for topic in sorted({r['topic'] for r in splits['test']})}
    artifact={'vectorizer':vectorizer,'classifier':classifier,'task':'pairwise_argument_convincingness',
              'corpus_license':'CC-BY-4.0','not_an_essay_grader':True}
    model_path=output/'argument-quality.joblib';joblib.dump(artifact,model_path,compress=3)
    shutil.copyfile(prepared/'source-attribution.json',output/'source-attribution.json')
    (output/'ATTRIBUTION.md').write_text('# Training data attribution\n\n'+SOURCE['citation']+'\n\n'+SOURCE['repository']+'\n\nData: CC BY 4.0. Original CreateDebate arguments: CC BY 3.0; ConvinceMe arguments: public domain, per corpus authors. See source-attribution.json for original author/debate links.\n\nThis is an experimental convincingness comparator, not a teacher-calibrated analytical-writing grader or factual verifier.\n')
    ids={name:[r['id'] for r in records] for name,records in splits.items()}
    (output/'split-ids.json').write_text(json.dumps(ids,indent=2)+'\n')
    (output/'test-predictions.jsonl').write_text(''.join(json.dumps({'id':r['id'],'topic':r['topic'],'gold':r['label'],'prediction':'a1' if p else 'a2'})+'\n' for r,p in zip(splits['test'],pred)))
    report={'task':'pairwise_argument_convincingness','model':'TF-IDF word/character differences + logistic regression',
        'training_performed':True,'large_language_model_trained':False,'teacher_grades':False,
        'production_grader_approved':False,
        'promotion_decision':'Not an analytical grader; deployment requires independent task-matched validation. Compare all recorded baselines before interpreting results.',
        'commercial_data_license':'CC-BY-4.0','source':SOURCE,'source_pair_count':len(rows),
        'splits':{k:{'pairs':len(v),'topics':len({r['topic'] for r in v})} for k,v in splits.items()},
        'split_policy':'Debate-topic holdout, both stances grouped; cross-split exact argument duplicates removed. No claim of author-disjointness.',
        'removed_cross_split_pairs':removed,'validation_candidates':candidates,'selected_C':chosen,
        'test':metrics(ytest,pred),'majority_baseline':metrics(ytest,np.full(len(ytest),majority)),
        'longer_argument_baseline':metrics(ytest,length_predictions),'test_by_topic':per_topic,
        'trained_model_beats_longer_argument_baseline':float((pred==ytest).mean())>float((length_predictions==ytest).mean()),
        'tie_count':int((np.abs(margin)<1e-8).sum()),'artifact_sha256':digest(model_path.read_bytes()),
        'runtime_seconds':time.monotonic()-start,'versions':{'python':platform.python_version(),'scikit_learn':sklearn.__version__,'numpy':np.__version__},
        'limitations':['Crowd convincingness is not teacher-scored analytical reasoning.','Persuasive arguments can still be factually wrong.',
            'No source-passage fidelity or warrant validity labels.','No tutoring conversations or student-revision outcome evaluation.',
            'A small topic holdout and public benchmark cannot establish production fairness or robust generalization.',
            'The component is not automatically deployed or substituted for analytical grades.']}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args()
    try:
        report=train(args.prepared,args.out)
        print(json.dumps({k:report[k] for k in ('training_performed','splits','selected_C','test','majority_baseline','longer_argument_baseline','runtime_seconds')},indent=2))
    except (ValueError,OSError) as exc:parser.exit(2,str(exc)+'\n')


if __name__=='__main__':main()
