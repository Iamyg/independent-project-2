"""Check archived job evidence, recompute timing statistics and audit final report."""
import hashlib
import json
import statistics
from decimal import Decimal
from pathlib import Path
from docx import Document
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def save(path, obj):
    (ROOT / path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

bench = read('results/latest-benchmark.json')
functional = read('results/summary.json')
jar = ROOT / 'generated/generated-code/target/generated-code-1.0-SNAPSHOT-jar-with-dependencies.jar'
assert sha(jar) == bench['query_jar_sha256']
assert sha(ROOT / 'queries/q3.sql') == bench['query_sql_sha256']
ids = set()
for category in ['micro', 'tpch']:
    batch = read('results/latest-' + category + '.json')
    for row in batch['results']:
        folder = ROOT / batch['batch'] / row['name']
        job = read(folder / 'flink-job.json')
        comparison = read(folder / 'comparison.json')
        assert job['state'] == 'FINISHED' and job['jid'] == row['job_id']
        assert comparison['status'] == 'passed' and not comparison['differences']
        assert row['query_jar_sha256'] == bench['query_jar_sha256']
        ids.add(row['job_id'])
assert len(ids) == functional['total'] == functional['passed'] == 28

for row in bench['runs']:
    folder = ROOT / row['directory']
    job = read(folder / 'flink-job.json')
    comparison = read(folder / 'comparison.json')
    assert job['state'] == 'FINISHED' and job['jid'] == row['job_id']
    assert job['duration'] == row['flink_duration_ms']
    assert comparison['status'] == 'passed' and not comparison['differences']
    assert max(v['parallelism'] for v in job['vertices']) == row['parallelism']
    assert sha(ROOT / row['input']) == row['input_sha256']
    assert (folder / 'raw-output').is_file()
    actual = read(folder / 'actual.json')
    expected = read(Path(row['input']).parent / 'reference.json')
    # Cross-check archived normalized answers independently of the status flag.
    a = {tuple(x[:3]): Decimal(x[3]) for x in actual}
    e = {tuple(x[:3]): Decimal(x[3]) for x in expected}
    assert a.keys() == e.keys()
    assert all(abs(a[k] - e[k]) <= max(Decimal('1e-6'), Decimal('1e-9') * abs(e[k])) for k in e)
    assert row['job_id'] not in ids
    ids.add(row['job_id'])
assert len(ids) == 60

for row in bench['summary']:
    runs = [r for r in bench['runs'] if not r['warmup'] and
            all(r[k] == row[k] for k in ['scale_factor', 'scenario', 'parallelism'])]
    times = [r['flink_duration_ms'] for r in runs]
    assert len(times) == row['measured_runs'] == 3
    assert (statistics.median(times), min(times), max(times)) == (row['median_ms'], row['min_ms'], row['max_ms'])

report = ROOT / 'report/Cquirrel_Q3_Reproduction_Report.pdf'
editable = ROOT / 'report/Cquirrel_Q3_Reproduction_Report.docx'
pdf = PdfReader(report)
assert len(pdf.pages) == 7
text = '\n'.join(p.extract_text() for p in pdf.pages)
sections = ['Background of the project and related work', 'Description of the query and the algorithm',
            'Implementation details', 'Experimental setup and data sets used',
            'Experimental results and discussion', 'Future directions']
assert all(s in text for s in sections)
assert 'R2T' not in text and '\ufffd' not in text
document = Document(editable)
rows = sorted(bench['summary'], key=lambda r: (r['scale_factor'], r['scenario'] != 'insert', r['parallelism']))
assert len(document.tables) == 4
for dr, r in zip(document.tables[3].rows[1:], rows):
    assert dr.cells[3].text == str(r['median_ms'])
    assert dr.cells[4].text == str(r['min_ms']) + '-' + str(r['max_ms'])
    assert dr.cells[5].text == f"{r['speedup_vs_p1']:.3f}"
assert len(document.tables[3].rows) == 9
for n in range(1, len(pdf.pages) + 1): assert (ROOT / f'report/rendered/final-{n}.png').is_file()

save('report/qa.json', {
    'status': 'passed', 'page_count': len(pdf.pages), 'required_page_range': [4, 8],
    'required_sections_present': sections, 'table_values_match_archived_measurements': True,
    'pdf_sha256': sha(report), 'docx_sha256': sha(editable),
    'rendering': 'Microsoft Word PDF export + bundled Poppler 125 dpi',
    'fallback_reason': 'Packaged render_docx.py could not find soffice.exe; Word was available.',
    'visual_review': {'pages_reviewed': list(range(1, len(pdf.pages) + 1)), 'reviewer': 'assistant',
                      'result': 'All final page PNGs inspected: no clipping, overlapping, missing glyphs or sparse overflow page.'},
})
save('provenance/simple-repro-audit.json', {
    'status': 'passed', 'functional_jobs': 28, 'benchmark_jobs': 32,
    'warmup_jobs': sum(r['warmup'] for r in bench['runs']),
    'measured_jobs': sum(not r['warmup'] for r in bench['runs']),
    'unique_finished_flink_jobs': len(ids), 'passed_comparisons': 60,
    'benchmark_input_hashes_verified': True, 'timing_configurations_recomputed': 8,
    'benchmark_normalized_answers_rechecked': 32, 'report_pages': len(pdf.pages),
    'report_table_values_checked': 8, 'query_jar_sha256': sha(jar),
    'scope': 'Q3 functionality plus small single-machine runtime experiment; no cross-system performance claim',
})
paths = []
for path in sorted(ROOT.rglob('*')):
    if not path.is_file(): continue
    rel = path.relative_to(ROOT).as_posix()
    if '__pycache__' in path.parts or rel.startswith(('cache/pip/', 'report/reference/')): continue
    if rel.startswith('report/rendered/') and not path.name.startswith('final-'): continue
    if rel == 'provenance/simple-repro-manifest.json': continue
    paths.append({'path': rel, 'bytes': path.stat().st_size, 'sha256': sha(path)})
save('provenance/simple-repro-manifest.json', {'algorithm': 'SHA-256', 'files': paths})
print(json.dumps({'status': 'passed', 'finished_jobs': len(ids), 'report_pages': len(pdf.pages),
                  'manifest_entries': len(paths)}, ensure_ascii=False))
