"""Commercially licensed human argument-quality data, kept in its native task."""
import argparse
from collections import Counter
import hashlib
import html
import io
import json
from pathlib import Path
import re
from urllib.request import urlopen
import xml.etree.ElementTree as ET
import zipfile

SOURCE = {
    'repository':'https://github.com/UKPLab/acl2016-convincing-arguments',
    'commit':'ca9d24e41b8805ff2e1d3585d552b49bb64a65f7',
    'archive_sha256':'2eabdbf837449ca21e40775b66094d2c9cb37119b5d5d0190ab422ee6307f5b0',
    'license':'CC-BY-4.0',
    'citation':'Ivan Habernal and Iryna Gurevych (2016). Which argument is more convincing? Analyzing and predicting convincingness of Web arguments using bidirectional LSTM. ACL, 1589–1599.',
    'paper':'https://aclanthology.org/P16-1150/',
    'source_argument_licenses':['CC-BY-3.0 (CreateDebate)','Public domain (ConvinceMe), as documented by corpus authors'],
    'label_origin':'Human crowdsourcing, aggregated by the corpus authors; not teacher grades.',
    'scope':'Pairwise convincingness, not factual correctness, source-grounded analytical grading or tutoring efficacy.',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def clean_text(text):
    return ' '.join(html.unescape(re.sub(r'<[^>]*>',' ',text or '')).split())


def text_hash(text):
    return digest(' '.join(text.casefold().split()).encode())


def download(output):
    root=Path(output)
    root.mkdir(parents=True,exist_ok=False)
    url=f"https://codeload.github.com/UKPLab/acl2016-convincing-arguments/zip/{SOURCE['commit']}"
    with urlopen(url,timeout=90) as response:
        data=response.read()
    if digest(data)!=SOURCE['archive_sha256']:
        raise ValueError('Source archive checksum differs from the pinned reviewed release.')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for member in archive.infolist():
            if member.is_dir():continue
            relative=Path(*Path(member.filename).parts[1:])
            # Only the authors' data and README are needed; do not import their
            # unrelated third-party experimental code or its dependencies.
            if not (str(relative).startswith('data/') or str(relative)=='README.md'):continue
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('Invalid archive path.')
            dest=root/'source'/relative
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(archive.read(member))
    (root/'source.zip').write_bytes(data)
    manifest={**SOURCE,'archive_url':url,'archive_bytes':len(data)}
    (root/'download-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def read_pairs(directory):
    root=Path(directory)
    archive=root/'source.zip'
    if digest(archive.read_bytes())!=SOURCE['archive_sha256']:
        raise ValueError('Source archive failed integrity verification.')
    # Read the reviewed bytes, not potentially modified loose extractions.
    pairs=[];attribution={};seen=set()
    with zipfile.ZipFile(archive) as z:
        names=sorted(n for n in z.namelist() if '/data/UKPConvArg1Strict-XML/' in n and n.endswith('.xml'))
        if len(names)!=32:raise ValueError('Expected all 32 published strict corpus files.')
        for name in names:
            for node in ET.fromstring(z.read(name)):
                label=node.findtext('goldLabel')
                if label not in ('a1','a2'):raise ValueError('Unexpected native label in strict corpus.')
                a,b=clean_text(node.findtext('arg1/text')),clean_text(node.findtext('arg2/text'))
                if not a or not b or a==b:continue
                original_id=node.findtext('id')
                record_id=digest((name+'|'+original_id).encode())[:24]
                if record_id in seen:raise ValueError('Duplicate corpus pair.')
                seen.add(record_id)
                reasons=[]
                votes=[]
                for worker in node.findall('mTurkAssignments/mTurkAssignment'):
                    vote=worker.findtext('value');votes.append(vote)
                    reason=clean_text(worker.findtext('reason'))
                    try:competence=float(worker.findtext('turkCompetence') or '0')
                    except ValueError:competence=0
                    if vote==label and competence>=.8 and 10<=len(reason)<=2000:
                        reasons.append(reason)
                if len(votes)<3:raise ValueError('Insufficient original human votes.')
                topic=clean_text(node.findtext('debateMetaData/title'))
                if not topic:raise ValueError('Missing debate group.')
                pair={'id':record_id,'topic':topic,'a1':a,'a2':b,'label':label,
                    'human_vote_count':len(votes),'human_agreement_fraction':sum(v==label for v in votes)/len(votes),
                    'human_reasons':list(dict.fromkeys(reasons)), 'label_origin':SOURCE['label_origin'],'license':SOURCE['license']}
                pairs.append(pair)
                for field,text in (('arg1',a),('arg2',b)):
                    credit={'author_url':node.findtext(field+'/author'),
                        'source_debate_url':node.findtext('debateMetaData/url'),'source_argument_id':node.findtext(field+'/id')}
                    credits=attribution.setdefault(text_hash(text),[])
                    if credit not in credits:credits.append(credit)
    return pairs,attribution


def prepare(directory,output):
    pairs,attribution=read_pairs(directory)
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    (out/'pairs.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in pairs))
    (out/'source-attribution.json').write_text(json.dumps(attribution,indent=2)+'\n')
    report={**SOURCE,'pair_count':len(pairs),'unique_arguments':len(attribution),
        'topic_count':len(set(r['topic'] for r in pairs)),
        'pairs_with_agreeing_human_explanations':sum(bool(r['human_reasons']) for r in pairs),
        'votes_per_pair':dict(Counter(str(r['human_vote_count']) for r in pairs)),
        'pairs_sha256':digest((out/'pairs.jsonl').read_bytes()),'training_performed':False,
        'commercial_data_eligible':True,'teacher_grades':False,'source_based_essay_grades':False}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['download','prepare'])
    parser.add_argument('--source',default='model_work/data/public/convarg')
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    try:
        result=download(args.out) if args.command=='download' else prepare(args.source,args.out)
        print(json.dumps(result,indent=2))
    except (ValueError,OSError) as exc:parser.exit(2,str(exc)+'\n')


if __name__=='__main__':main()
