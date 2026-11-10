"""Build the English seven-page report from archived experiment results.

Run with the Codex bundled Python (python-docx, reportlab and pypdf).
The PDF is exported from this DOCX by export_report.ps1, then visually checked.
"""
import json
import subprocess
from pathlib import Path
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from reportlab.graphics.shapes import Drawing, Rect, Line, String
from reportlab.graphics import renderPDF
from reportlab.lib import colors

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'report'
FIG = OUT / 'figures'
FIG.mkdir(exist_ok=True)
B = json.loads((ROOT / 'results/latest-benchmark.json').read_text(encoding='utf-8'))
S = json.loads((ROOT / 'results/summary.json').read_text(encoding='utf-8'))
assert S['total'] == S['passed'] == 28
assert len(B['runs']) == 32 and all(r['status'] == 'passed' for r in B['runs'])
ROWS = sorted(B['summary'], key=lambda r: (r['scale_factor'], r['scenario'] != 'insert', r['parallelism']))
RUNTIME = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies'

# A static research figure. Bars show medians; whiskers show min/max, not CI.
d = Drawing(500, 224)
left, bottom, width, height = 48, 43, 430, 152
for value in range(0, 901, 150):
    y = bottom + height * value / 900
    d.add(Line(left, y, left + width, y, strokeColor=colors.HexColor('#dddddd'), strokeWidth=0.4))
    d.add(String(left - 8, y - 3, str(value), textAnchor='end', fontName='Helvetica', fontSize=9))
d.add(String(left, 211, 'Flink job duration (ms)', fontName='Helvetica', fontSize=10))
palette = ['#484848', '#aeb8c2']
for i, label in enumerate(['SF .001 / insert', 'SF .001 / delete', 'SF .01 / insert', 'SF .01 / delete']):
    center = left + (i + 0.5) * width / 4
    d.add(String(center, 26, label, textAnchor='middle', fontName='Helvetica', fontSize=9))
    for j in range(2):
        row = ROWS[2 * i + j]
        x = center + (j - 0.5) * 30
        y = bottom + height * row['median_ms'] / 900
        d.add(Rect(x - 12, bottom, 24, y - bottom, fillColor=colors.HexColor(palette[j]), strokeColor=None))
        ymin = bottom + height * row['min_ms'] / 900
        ymax = bottom + height * row['max_ms'] / 900
        d.add(Line(x, ymin, x, ymax, strokeColor=colors.black, strokeWidth=0.8))
        for yy in [ymin, ymax]:
            d.add(Line(x - 4, yy, x + 4, yy, strokeColor=colors.black, strokeWidth=0.8))
        d.add(String(x, ymax + 5, str(row['median_ms']), textAnchor='middle', fontName='Helvetica', fontSize=9))
for j in range(2):
    d.add(Rect(345 + 70 * j, 208, 10, 8, fillColor=colors.HexColor(palette[j]), strokeColor=None))
    d.add(String(360 + 70 * j, 208, 'p = ' + str(j + 1), fontName='Helvetica', fontSize=9))
d.add(String(262, 7, 'Bars: median; whiskers: min-max of 3 measured runs', textAnchor='middle', fontName='Helvetica', fontSize=9))
renderPDF.drawToFile(d, str(FIG / 'runtime.pdf'))
subprocess.run([str(RUNTIME / 'native/poppler/Library/bin/pdftoppm.exe'), '-png', '-singlefile', '-r', '180',
                str(FIG / 'runtime.pdf'), str(FIG / 'runtime')], check=True)

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.top_margin, sec.bottom_margin = Cm(2.15), Cm(2.0)
sec.left_margin = sec.right_margin = Cm(2.4)
sec.footer_distance = Cm(1.0)

def fonts(style, size, bold=False, east='Times New Roman'):
    st = doc.styles[style]
    st.font.name = 'Times New Roman'
    st.font.size = Pt(size)
    st.font.bold = bold
    st.font.color.rgb = RGBColor(0, 0, 0)
    st.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), east)
    for attr in ['asciiTheme', 'hAnsiTheme', 'eastAsiaTheme', 'cstheme']:
        st.element.rPr.rFonts.attrib.pop(qn('w:' + attr), None)
    for border in st.element.findall('.//' + qn('w:pBdr')):
        border.getparent().remove(border)
    pf = st.paragraph_format
    pf.space_after = Pt(6)
    pf.line_spacing = 1.15

fonts('Normal', 11)
fonts('Title', 18, True, 'Arial')
fonts('Heading 1', 14, True, 'Arial')
fonts('Heading 2', 11.5, True, 'Arial')
fonts('Caption', 9.5)
doc.styles['Caption'].font.italic = False
doc.styles['Heading 1'].paragraph_format.space_before = Pt(8)
doc.styles['Heading 2'].paragraph_format.space_before = Pt(6)
doc.core_properties.title = 'Cquirrel: Continuous Query Processing over Acyclic Relational Schemas'
doc.core_properties.subject = 'Q3 correctness and small-scale Flink runtime experiment'
doc.core_properties.author = 'Chai Guanpeng'

foot = sec.footer.paragraphs[0]
foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
field = OxmlElement('w:fldSimple')
field.set(qn('w:instr'), 'PAGE')
foot._p.append(field)

def p(text, style=None, align=None):
    para = doc.add_paragraph(text, style)
    if align is not None:
        para.alignment = align
    return para

def h(text, level=1):
    return doc.add_heading(text, level)

def page():
    doc.add_page_break()

def caption(text):
    return p(text, 'Caption', WD_ALIGN_PARAGRAPH.CENTER)

def table(headers, rows, widths=None, size=10):
    t = doc.add_table(rows=1, cols=len(headers))
    t.autofit = False
    if widths:
        for col, w in zip(t.columns, widths): col.width = Cm(w)
    pr = t._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for side in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        e = OxmlElement('w:' + side)
        e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), '4'); e.set(qn('w:color'), 'C9C9C9')
        borders.append(e)
    pr.append(borders)
    margin = OxmlElement('w:tblCellMar')
    for side in ['top', 'left', 'bottom', 'right']:
        e = OxmlElement('w:' + side); e.set(qn('w:w'), '65'); e.set(qn('w:type'), 'dxa'); margin.append(e)
    pr.append(margin)
    for i, value in enumerate(headers): t.rows[0].cells[i].text = value
    for row in rows:
        for cell, value in zip(t.add_row().cells, row): cell.text = str(value)
    for ri, row in enumerate(t.rows):
        keep = OxmlElement('w:cantSplit'); row._tr.get_or_add_trPr().append(keep)
        if ri == 0:
            repeat = OxmlElement('w:tblHeader'); row._tr.get_or_add_trPr().append(repeat)
        for ci, cell in enumerate(row.cells):
            if widths: cell.width = Cm(widths[ci])
            if ri == 0:
                shade = OxmlElement('w:shd'); shade.set(qn('w:fill'), 'F0F0F0'); cell._tc.get_or_add_tcPr().append(shade)
            for para in cell.paragraphs:
                para.paragraph_format.space_after = Pt(0)
                para.paragraph_format.line_spacing = 1.1
                for run in para.runs:
                    run.font.size = Pt(size); run.bold = (ri == 0)
    p('').paragraph_format.space_after = Pt(0)
    return t

def code(text, size=9):
    para = p('')
    para.paragraph_format.space_after = Pt(7)
    para.paragraph_format.line_spacing = 1.0
    run = para.add_run(text)
    run.font.name = 'Consolas'; run.font.size = Pt(size)
    shade = OxmlElement('w:shd'); shade.set(qn('w:fill'), 'F6F6F6'); para._p.get_or_add_pPr().append(shade)
    return para


# Page 1: title, abstract and background.
p('Cquirrel: Continuous Query Processing\nover Acyclic Relational Schemas', 'Title', WD_ALIGN_PARAGRAPH.CENTER)
p('Student ID: 21185592\nStudent name: Chai Guanpeng', align=WD_ALIGN_PARAGRAPH.CENTER)
h('Abstract', 2)
p('This project reproduces the three-table Q3 example in Cquirrel using the authors\' code generator and core implementation on Flink under Windows and WSL2. Correctness is checked with 22 small scenarios and six TPC-H scenarios, covering insertion, deletion, restoration, late data and predicate boundaries. A further 32 runs examine two data scales, two workloads and two parallelism settings. All jobs pass final-result validation against independent SQL answers. Increasing parallelism from one to two does not reduce median job duration in this small, single-machine experiment. The deliverables include executable query code, repeatable experiments, raw evidence and a report of the observed limitations.')
p('Keywords: Cquirrel; incremental view maintenance; multiway joins; Flink; TPC-H', 'Caption')
h('1. Background of the project and related work')
h('1.1 Motivation and reproduction objectives', 2)
p('When customer, order and line-item records change continuously, revenue statistics must also change. Recomputing a complete join and aggregation after every update can repeatedly scan unchanged data. Incremental view maintenance retains state and processes the affected portion. Cquirrel targets queries whose foreign-key relationships form a directed acyclic graph and whose joins equate primary and foreign keys; it compiles maintenance logic into Flink programs [1].')
p('This simple reproduction asks whether the official implementation correctly maintains the final Q3 answer in the available environment, and how job duration changes with parallelism at scale factors 0.001 and 0.01. It reuses the official algorithm and adds data generation, execution and validation tools. Cross-system rankings, failure recovery and reproduction of every paper figure are outside this scope.')
h('1.2 Related work', 2)
p('DBToaster recursively derives higher-order deltas and materializes auxiliary views to reduce maintenance cost [3]. Trill combines a temporal relational model with batched columnar representations and dynamic compilation for diverse analytical workloads [4]. These systems also address changing data, but use different query models and execution approaches. They were not deployed as performance baselines here; the measurements compare configurations of the same Cquirrel program.')

# Pages 2-3: expanded algorithm description, synchronized with the Chinese edition.
page()
h('2. Description of the query and the algorithm')
h('2.1 Query semantics', 2)
p('The query is the Q3 variant in Section 2 of the paper. It selects AUTOMOBILE customers, orders placed before 1995-03-13 and line items shipped after that date. Discounted revenue is grouped by order key, order date and shipping priority. There is no ORDER BY or LIMIT: every qualifying group is returned, rather than the full standard TPC-H Q3 Top-10 output.')
code((ROOT / 'queries/q3.sql').read_text(encoding='utf-8').strip(), 9)
h('2.2 Join direction and live-state conditions', 2)
p('The foreign-key direction is Lineitem -> Orders -> Customer, while update propagation runs in the opposite direction. For this chain, a record is live when it exists, passes its local predicate and can join to the required parent. The conditions are recursive:')
p('A customer is live if it exists and belongs to AUTOMOBILE.\nAn order is live if it exists, predates the boundary and has a live customer.\nA line item is live if it exists, ships after the boundary and has a live order.')
p('Receiving a line item therefore does not immediately imply a revenue contribution. If its order or customer has not arrived, it cannot yet form a complete join. It can enter the result later when its parent becomes live. This explanation applies to the Q3 chain; a general DAG with converging paths additionally requires consistency between matches along those paths [1].')
p('Customer  ->  Orders  ->  Lineitem  ->  Aggregate  ->  File sink', align=WD_ALIGN_PARAGRAPH.CENTER)
caption('Figure 1. Update propagation in the generated Q3 program.')
h('2.3 Maintained state and indexes', 2)
p('Logically, the order layer needs a customer-key-to-orders index, while the line-item layer needs an order-key-to-line-items index. The operators also retain parent liveness and the attributes needed by the join. Records that pass local predicates but lack a live parent remain available for later activation. The aggregation layer stores current revenue for each order.')
p('In the generated Job.scala, customer and order streams meet on the customer key. Order outputs and line-item inputs then meet on the order key, which also partitions aggregation [2]. Related records and updates therefore reach the same keyed state. A parent change visits its indexed dependants without scanning unrelated customers or orders.')

page()
h('2.4 Insertion and deletion propagation', 2)
p('Consider a newly inserted customer. The Q3 maintenance logic can be explained in four steps. In the actual program, separate Flink operators exchange messages asynchronously; a single function does not execute the entire sequence.')
p('First, test the AUTOMOBILE predicate and update the customer key\'s live state. Second, locate stored orders under that key. Orders passing the date predicate become joinable and notify the next operator with their order keys, dates and priorities. Third, locate the corresponding line items and emit join additions for those passing the shipment-date predicate. Fourth, calculate their revenue contributions and update each affected order aggregate.')
p('A line item arriving before its order is retained until that order becomes live. When the parent is already live, a new qualifying order or line item can propagate immediately. A record failing its local predicate contributes nothing to the query.')
p('Deletion retracts previous contributions. Deleting a live line item removes only its contribution. Deleting a live customer invalidates the associated orders and their line items, generating removals downstream. This does not delete the original order or line-item records from their input relations: they can remain waiting and be reconsidered when the parent is restored.')
h('2.5 Updating the aggregate', 2)
p('Let g=(order key, order date, shipping priority), let A[g] be its current revenue, and let w(l)=l_extendedprice*(1-l_discount). A join addition has sign s=+1 and a removal has s=-1. Each join change performs:')
p('A[g] <- A[g] + s * w(l)', align=WD_ALIGN_PARAGRAPH.CENTER)
p('QAggregate0ProcessFunction supplies the contribution function, addition and subtraction to the core aggregate operator, which stores A[g] in ValueState. This version emits the updated A[g], not s*w(l). Consequently, summing every amount in the output file would be incorrect. Section 3 explains empty groups and floating-point tolerance.')
h('2.6 Worked example, cost and validation target', 2)
p('Suppose order 101 has two qualifying contributions, 900 and 400. Insertion gives 0+900+400=1300. Deleting the first line item gives 1300-900=400. Deleting the customer retracts the remaining 400 and removes the order from the query answer. Restoring the customer reactivates the remaining contribution of 400. The six tested lifecycle prefixes therefore expect: no group -> 900 -> 1300 -> 400 -> no group -> 400.')
p('Indexes restrict work to affected keys, avoiding complete join recomputation. However, deleting a customer with many dependent orders and line items can still produce many retractions; total processing and output cost is not always O(1). Each emitted join change requires one arithmetic update to SUM.')
p('Each lifecycle prefix is replayed independently from empty state and checked after completion. This validates the resulting states without requiring every asynchronous output to follow input-event order. Additional insertion, deletion, late-parent and restoration cases check these transitions; Section 5 reports the coverage and results.')

# Page 4: implementation.
page()
h('3. Implementation details')
h('3.1 Official implementation and project additions', 2)
p('The reproduction pins Cquirrel-release commit 501cfde6dc2968cfccee992ab4f298c499cc8028 [2]. The pipeline is SQL -> JSON plan -> Scala operators -> Maven JAR -> Flink job. Relation and aggregation maintenance use the authors\' implementation; this project adds repeatable execution, datasets and independent validation.')
caption('Table 1. Main implementation artifacts; see FILES.md for the full inventory.')
table(['Artifact', 'Role in this reproduction'], [
    ['queries/q3.sql; q3.generated.json', 'Define query semantics and retain the official parser output.'],
    ['generated/.../Job.scala', 'Connect operators; adapt input/output arguments and text formatting.'],
    ['Qcustomer / Qorders / Qlineitem /\nQAggregate0ProcessFunction.scala', 'Generated relation and aggregate operators using the original core JAR.'],
    ['scripts/experiment.py', 'Generate scenarios, replay updates and compare with SQL answers.'],
    ['scripts/benchmark.py;\nconfigs/benchmark.json', 'Schedule scales, warm-ups and repetitions; validate results and summarize time.'],
    ['patches/job-cli-output.patch', 'Expose the changes to the generated job entry point.'],
], [6.6, 9.6], 9.5)
h('3.2 Compatibility and output semantics', 2)
p('The official SQL parser matches aggregate names case-sensitively. Uppercase SUM omits aggregation metadata; code generation can print an exception yet return a successful exit code. The reproduction uses the equivalent lowercase sum and checks the plan, generated files and JAR explicitly. The failed attempt remains archived.')
p('The aggregate emits updated group revenue, rather than an additive delta. The adapted format is order key|date|priority|revenue|source event number. Normalization retains the last arriving value per group. Source event numbers may be non-monotonic and must not reorder outputs. A single-parallelism file sink preserves arrival order.')
p('After the last contribution is removed, the core may emit zero or a small floating-point residual, whereas SQL removes the group. All contributions in this experiment are strictly positive, so final absolute revenue at most 1e-6 is recorded as an empty-group sentinel. This convention does not generalize to valid zero revenue, negative contributions or cancellation in arbitrary SUM queries.')
h('3.3 Independent correctness checks', 2)
p('Functional tests replay events into primary-key dictionaries, load final tables into DuckDB and execute the same SQL. Small cases additionally use hand-calculated answers. Timing cases query the generated database directly, excluding selected keys for deletion workloads. Group keys must match exactly; Cquirrel Double values are checked against DECIMAL reference amounts using:')
p('|actual - reference| <= max(1e-6, 1e-9 * |reference|).', align=WD_ALIGN_PARAGRAPH.CENTER)

# Page 5: setup.
page()
h('4. Experimental setup and data sets used')
h('4.1 Execution environment', 2)
caption('Table 2. Experimental environment.')
table(['Component', 'Configuration'], [
    ['System and hardware', 'Windows host; WSL2 / Ubuntu 20.04; Intel Core i7-14700HX; 28 logical CPUs and approximately 7.6 GiB visible RAM.'],
    ['Build and runtime', 'OpenJDK 1.8.0_452; Maven 3.6.3; Flink 1.11.2 / Scala 2.12.'],
    ['Scripts and generator', 'Python 3.8.10; DuckDB 1.1.3; signed official TPC-H extension.'],
    ['Flink resources', 'One TaskManager, two slots; JobManager 1024 MB and TaskManager 1728 MB; operator parallelism p=1 or 2; file source/sink parallelism fixed at 1.'],
], [3.5, 12.7], 9.5)
h('4.2 Datasets and update workloads', 2)
p('The DuckDB TPC-H extension generates synthetic data [5]; only Customer, Orders and Lineitem feed Q3. Generator versions, extension hashes, input hashes and deletion rules are archived. SF is a generation parameter; actual row counts below describe the input more precisely than an estimated file size.')
caption('Table 3. Source rows and workload event counts.')
table(['SF', 'Customers', 'Orders', 'Line items', 'Insertions', 'Deletions'], [
    ['0.001', '150', '1,500', '6,005', '7,655', '601'],
    ['0.01', '1,500', '15,000', '60,175', '76,675', '6,018'],
], [1.5, 2.6, 2.5, 3.0, 3.3, 3.3], 9.5)
p('The insert workload loads all customers, orders and line items in that order. The delete_10pct workload then removes every tenth line item in (orderkey, linenumber) order. Rounding makes the deletion share approximately 10%; total event counts are 8,256 and 82,693. These are deterministic deletions after insertion, not randomly interleaved updates.')
h('4.3 Procedure and timing definition', 2)
p('First run 22 small scenarios and six SF=0.001 functional scenarios. Then evaluate 2 scales x 2 workloads x 2 parallelism settings: eight configurations, each with one warm-up and three measured runs. Within each measurement round, configuration order is shuffled using seed 20261023. All 32 runs must finish, apply the requested parallelism and pass answer validation; logs and raw outputs are retained.')
p('The primary metric is Flink REST job duration, including deployment, input, operators and file output. It excludes data generation, compilation and the complete client startup overhead. Client wall-clock time is stored separately. Tables use the median and minimum/maximum of three measured runs, excluding warm-up. This is neither per-update latency nor sustained streaming throughput.')
code('.\\repro_final\\run.ps1 all\n.\\repro_final\\run.ps1 benchmark', 9.5)

# Page 6: results.
page()
h('5. Experimental results and discussion')
h('5.1 Correctness', 2)
p('All 22 small scenarios, six TPC-H functional scenarios and 32 timing runs pass final-result validation: 60 verified Flink jobs in total. Small cases agree with hand calculations. Across the six first-stage TPC-H cases, the maximum absolute error for retained groups is 1e-11, within tolerance. Six verifier self-checks cover wrong amounts, missing/extra groups, floating-point tolerance, arrival order and empty-group sentinels.')
p('In timing runs, both SF=0.001 workloads end with 11 groups. At SF=0.01, insertion ends with 107 and deletion with 101. Equal group counts do not imply unchanged revenue: values are also checked. Parent deletion and restoration cases support correctness of cross-table propagation within the tested coverage.')
h('5.2 Job duration', 2)
caption('Table 4. Three measured runs per row; speedup = T1 / Tp.')
table(['SF', 'Workload', 'p', 'Median/ms', 'Min-max/ms', 'Speedup'], [
    [str(r['scale_factor']), 'Insert' if r['scenario'] == 'insert' else 'Insert + delete', r['parallelism'], r['median_ms'],
     str(r['min_ms']) + '-' + str(r['max_ms']), f"{r['speedup_vs_p1']:.3f}"] for r in ROWS
], [1.6, 3.3, 0.8, 3.1, 4.2, 3.2], 10)
pic = doc.add_picture(str(FIG / 'runtime.png'), width=Cm(15.7))
pic._inline.docPr.set('descr', 'Median job duration and minimum/maximum across three measured runs for eight configurations. No p=2 median is lower than its p=1 counterpart.')
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
caption('Figure 2. Bars show medians; whiskers show min/max, not confidence intervals.')

# Page 7: interpretation and references.
page()
h('5.3 Interpretation and limitations', 2)
p('At SF=0.01, increasing p from one to two changes median insertion time from 493 to 495 ms, and insertion-plus-deletion time from 549 to 713 ms. All four p=2 speedups are at most one: no parallel speedup is observed. At SF=0.001, jobs are shorter and run-to-run variation is larger relative to their duration.')
p('Small jobs may be dominated by deployment, scheduling and file I/O overhead. Two slots on one TaskManager are not independent machines; the source and sink remain serial, and additional parallelism can add communication overhead. These are plausible explanations, not isolated causal findings: no component-level profiling was performed. Three repetitions per configuration are insufficient for a robust significance assessment.')
p('Finite scenarios do not prove correctness in general. Empty-group handling assumes positive contributions. Bounded file replays do not measure continuous-stream latency, peak memory, checkpoint recovery or network failures. DuckDB is an answer oracle, not a timed competitor. The paper\'s scaling figure uses Q5, larger datasets and more workers [1]; this project uses Q3 with SF=0.001/0.01 and single-machine p=1/2. Results apply only to these conditions.')
h('6. Future directions')
p('First, extend to Q5, larger scale factors and multiple TaskManagers, with more repetitions and separate measurements of deployment, steady-state processing rate and update latency. Second, test randomly interleaved updates, skew, additional late-data cases and zero/negative contributions; maintain group counts or explicit retractions for general SUM semantics. Third, test checkpoints and recovery, and add other systems under matched semantics, hardware and timing definitions.')
p('The reproduction now provides a repeatable path from query generation to execution and independent validation. Per-run logs, raw outputs and summaries support traceability. The English package preserves the same measured evidence as the Chinese edition; translating documentation does not represent additional experiments. File roles and rerun commands are listed in README.md and report/FILES.md.')
h('References', 2)
refs = [
    '[1] Wang, Q., et al. Cquirrel: Continuous Query Processing over Acyclic Relational Schemas. PVLDB, 14(12): 2667-2670, 2021. DOI: 10.14778/3476311.3476315. https://www.cse.ust.hk/~yike/Cquirrel.pdf',
    '[2] HKUST Database Group. Cquirrel-release. Commit 501cfde6dc2968cfccee992ab4f298c499cc8028. https://github.com/hkustDB/Cquirrel-release (accessed 2026-10-23).',
    '[3] Ahmad, Y., Kennedy, O., Koch, C., Nikolic, M. DBToaster: Higher-order Delta Processing for Dynamic, Frequently Fresh Views. PVLDB, 5(10): 968-979, 2012. https://arxiv.org/abs/1207.0137',
    '[4] Chandramouli, B., et al. Trill: A High-Performance Incremental Query Processor for Diverse Analytics. Microsoft Research / VLDB publication. https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/trill-vldb2015.pdf',
    '[5] DuckDB. TPC-H Extension. https://duckdb.org/docs/stable/core_extensions/tpch (accessed 2026-10-23; experimental version: DuckDB 1.1.3).',
]
for text in refs:
    para = p(text)
    para.paragraph_format.line_spacing = 1.0
    para.paragraph_format.space_after = Pt(5)
    for run in para.runs: run.font.size = Pt(9)

target = OUT / 'Cquirrel_Q3_Reproduction_Report.docx'
doc.save(target)
(OUT / 'report-metadata.json').write_text(json.dumps({
    'benchmark_batch': B['batch'], 'benchmark_runs': len(B['runs']),
    'functional_jobs': S['total'], 'expected_pages': 7, 'language': 'en-US',
    'revision': 'Expanded algorithm: live states, keyed indexes, insert/delete propagation, aggregation and cost boundaries',
    'query_jar_sha256': B['query_jar_sha256'],
    'reference_layout': 'A4, centered title and student metadata, abstract, numbered academic sections, tables and references',
    'figures': ['figures/runtime.png'], 'authoring': 'python-docx; Word PDF export; Poppler raster verification',
}, ensure_ascii=False, indent=2), encoding='utf-8')
print(target)
