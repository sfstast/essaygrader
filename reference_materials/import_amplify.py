"""Import the user-supplied Amplify PDF as page-linked prompt reference excerpts.
Run: python reference_materials/import_amplify.py /path/to/Student_Work_Collection__Essay_Scoring.pdf
Requires pypdf on the importing workstation, not the website runtime.
"""
import hashlib
import json
from pathlib import Path
import sys


def import_pdf(path):
    from pypdf import PdfReader
    path = Path(path)
    reader = PdfReader(path)
    pages = [{'page': i + 1, 'text': page.extract_text() or ''} for i, page in enumerate(reader.pages)]
    if not pages or not any(p['text'].strip() for p in pages):
        raise ValueError('No extractable PDF text; OCR and manual review are required.')
    output = Path(__file__).parent / 'private' / 'amplify_pages.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        'source': 'Amplify Student Work Collection: Essay Scoring',
        'url': 'https://my.amplify.com/resources/wp-content/uploads/Student_Work_Collection__Essay_Scoring.pdf',
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'use': 'Qualitative prompt references with original labels; not user-rubric training labels.',
        'extraction_reviewed': False, 'pages': pages,
    }, ensure_ascii=False, indent=2) + '\n')
    print(f'Imported {len(pages)} pages to {output}. Review extraction before deployment.')


if __name__ == '__main__':
    import_pdf(sys.argv[1])
