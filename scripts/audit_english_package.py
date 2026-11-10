"""Verify English presentation and unchanged measured evidence in this copy."""
from pathlib import Path
import hashlib
import json
import re
import ast
import zipfile
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
COMPANION = ROOT.with_name('repro')
CJK = re.compile('[\u3400-\u9fff]')
TEXT_SUFFIXES = {'.py', '.md', '.json', '.scala', '.sql', '.sh', '.ps1', '.txt',
                 '.log', '.csv', '.xml', '.html', '.js', '.java', '.yml', '.yaml'}

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

violations = []
checked_text = 0
for path in ROOT.rglob('*'):
    if not path.is_file(): continue
    relative = path.relative_to(ROOT).as_posix()
    if CJK.search(relative): violations.append(relative + ': filename')
    if path.suffix.lower() in TEXT_SUFFIXES:
        content = path.read_text(encoding='utf-8', errors='replace')
        checked_text += 1
        if CJK.search(content): violations.append(relative + ': text')
    if path.suffix == '.py' and path.parent == ROOT / 'scripts':
        ast.parse(path.read_text(encoding='utf-8'))
    if path.suffix == '.docx':
        with zipfile.ZipFile(path) as archive:
            visible = archive.read('word/document.xml').decode('utf-8')
            if CJK.search(visible): violations.append(relative + ': document')
    if path.suffix == '.pdf':
        if CJK.search('\n'.join(page.extract_text() or '' for page in PdfReader(path).pages)):
            violations.append(relative + ': PDF')
assert not violations, violations

checked_evidence = 0
for group in ['data', 'results', 'queries', 'generated', 'tools']:
    for path in (ROOT / group).rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts: continue
        other = COMPANION / path.relative_to(ROOT)
        assert other.is_file(), str(other)
        assert sha(path) == sha(other), str(path)
        checked_evidence += 1
for name in ['experiment.py', 'benchmark.py', 'env.sh', 'repro.sh']:
    assert sha(ROOT / 'scripts' / name) == sha(COMPANION / 'scripts' / name)
relative = Path('vendor/Cquirrel-release/codegen/src/main/java/org/hkust/parser/Parser.java')
a = (ROOT / relative).read_text(encoding='utf-8')
b = (COMPANION / relative).read_text(encoding='utf-8')
assert re.sub(r'//[^\r\n]*', '', a) == re.sub(r'//[^\r\n]*', '', b)

record = {'status': 'passed', 'language': 'en-US', 'text_files_scanned': checked_text,
          'cjk_filename_or_content_violations': violations,
          'identical_experiment_artifacts': checked_evidence,
          'experiment_drivers_identical': True, 'parser_non_comment_source_identical': True,
          'report_pages': len(PdfReader(ROOT / 'report/Cquirrel_Q3_Reproduction_Report.pdf').pages),
          'new_experiment_runs_claimed': 0}
(ROOT / 'provenance/english-package-audit.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record))
