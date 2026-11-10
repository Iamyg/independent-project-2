"""Generate English summaries from archived results without changing evidence."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def write_report():
    out = ROOT / 'report'
    out.mkdir(exist_ok=True)
    summary = json.loads((ROOT / 'results/summary.json').read_text(encoding='utf-8'))
    lines = ['# First-stage experimental results', '',
             'Generated from saved Flink job and comparison records.', '',
             f"Total: {summary['total']} scenarios; passed: {summary['passed']}.", '',
             '| Category | Scenario | Status | Input events | Expected groups | Actual groups | Maximum absolute amount error |',
             '|---|---|---|---:|---:|---:|---:|']
    for r in summary['cases']:
        lines.append('| {} | {} | {} | {} | {} | {} | {} |'.format(
            r['category'], r['name'], r['status'], r['input_events'],
            r['expected_groups'], r['actual_groups'], r['max_absolute_error']))
    lines += ['', '## Expected answers and verification', '',
              'Order 101 lifecycle prefixes expect: no group -> 900 -> 1300 -> 400 -> no group -> 400. Each prefix is an independent replay from empty state; final results are checked after FINISHED against SQL and hand calculations.', '',
              'Require identical group keys. Amount tolerance is max(1e-6, 1e-9 * abs(reference)); Cquirrel uses Double and the SQL oracle uses DECIMAL.', '',
              'Near-zero final groups are recorded as empty-group sentinels. This assumes strictly positive contributions and is not a general SUM solution.', '',
              '## Artifacts and scope', '',
              'The retained chain is SQL -> plan -> Scala -> JAR -> Flink job -> raw output -> independent SQL answer -> comparison.', '',
              'Inputs use +CU/-CU, +OR/-OR and +LI/-LI for customer, order and line-item updates. Query constants are AUTOMOBILE and 1995-03-13.', '',
              'First-stage timings document execution only. Repeated timing experiments are reported separately in results/latest-benchmark.json and the final report. Q5 scalability, recovery and GUI reproduction are outside scope.', '',
              'See FILES.md for artifact roles and ../README.md for commands.']
    generation = json.loads((ROOT / 'data/tpch/source/generation.json').read_text(encoding='utf-8'))
    lines += ['', '## TPC-H input', '',
              f"Generator: DuckDB {generation['duckdb_version']} with the signed official TPC-H extension, SF={generation['scale_factor']}.", '',
              f"Rows: {generation['table_rows']}. Initial Q3 groups: {generation['initial_q3_groups']}.", '',
              'The database, three original table files, update streams and generation metadata are stored under data/tpch/.']
    (out / 'RESULTS.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    mappings = [
        ('README.md', 'Commands, assumptions and limitations', 'Entry point for reproducing and interpreting the experiment'),
        ('run.ps1', 'Windows PowerShell launcher', 'Dispatch each stage to Ubuntu-20.04'),
        ('scripts/env.sh; scripts/repro.sh', 'Runtime activation and stage dispatch', 'Resolve this package root and capture stage logs'),
        ('scripts/experiment.py', 'Functional experiment driver', 'Generate cases, build and run Q3, compute independent answers and compare results'),
        ('scripts/benchmark.py', 'Repeated timing driver', 'Validate eight configurations across 32 warm-up/measured runs'),
        ('scripts/write_report.py', 'English Markdown summaries', 'Refresh functional results and this artifact guide'),
        ('scripts/create_final_report.py', 'Word report and scientific figure builder', 'Turn archived measurements into the seven-page English report'),
        ('scripts/export_report.ps1', 'Hidden Word PDF export', 'Create the PDF from the editable report'),
        ('scripts/audit_final_artifacts.py', 'Evidence and report audit', 'Check 60 jobs, statistics, table values and final file hashes'),
        ('queries/q3.sql', 'The paper Q3 query', 'Shared semantics for Cquirrel and the SQL reference'),
        ('queries/q3.generated.json', 'Official parser output', 'Record joins, predicates and aggregate expressions before code generation'),
        ('configs/experiment.json', 'Source version, scale and tolerance', 'Fix functional-test conditions'),
        ('configs/benchmark.json', 'Scales, workloads, repetitions and seed', 'Fix timing-experiment conditions'),
        ('data/micro/*/events.txt; case.json', 'Small update sequences and hand answers', 'Check deletion, restoration, late parents, filtering and grouping'),
        ('data/tpch/source/', 'SF=0.001 tables and source database', 'Provide repeatable generated data for functional cases'),
        ('data/tpch/*/events.txt; case.json', 'Six TPC-H workloads', 'Test bulk insertion and updates across the three relations'),
        ('data/benchmark/sf*/', 'Timing datasets, input streams and SQL answers', 'Retain exact workloads, hashes and deletion rules'),
        ('generated/original/', 'Unmodified generated code and POM', 'Expose the baseline before entry-point adaptation'),
        ('generated/generated-code/src/main/scala/org/hkust/Job.scala', 'Flink graph and text input/output', 'Route updates through relation and aggregation operators'),
        ('generated/.../QcustomerProcessFunction.scala', 'Customer operator', 'Apply the AUTOMOBILE predicate and propagate customer effects'),
        ('generated/.../QordersProcessFunction.scala', 'Order operator', 'Maintain customer joins and order-date filtering'),
        ('generated/.../QlineitemProcessFunction.scala', 'Line-item operator', 'Maintain order joins and shipment-date filtering'),
        ('generated/.../QAggregate0ProcessFunction.scala', 'Revenue aggregate', 'Add and retract discounted line-item contributions'),
        ('generated/generated-code/pom.xml', 'Maven build configuration', 'Compile and package the generated Scala query'),
        ('generated/generated-code/target/*jar-with-dependencies.jar', 'Executable query JAR', 'The program actually submitted to Flink'),
        ('patches/job-cli-output.patch', 'Entry-point adaptation diff', 'Make path arguments and canonical output formatting reviewable'),
        ('vendor/Cquirrel-release/', 'Pinned official source and core JAR', 'Retain implementation and license; six parser comments are translated'),
        ('tools/codegen-1.0-SNAPSHOT.jar', 'Official compiled generator', 'Create query code from SQL/JSON'),
        ('tools/python/; tools/duckdb-extensions/', 'DuckDB and signed TPC-H extension', 'Generate datasets and execute independent reference SQL'),
        ('cache/wheels/; cache/pip/', 'Dependency caches', 'Retain installation inputs'),
        ('results/<category>/<batch>/<case>/flink.log; flink-job.json', 'Client logs and REST job records', 'Prove FINISHED state, JobID, duration and applied parallelism'),
        ('results/<category>/<batch>/<case>/raw-output', 'Unmodified operator output', 'Retain evidence before normalization'),
        ('results/<category>/<batch>/<case>/reference.duckdb; reference.json', 'Final tables and SQL answers', 'Provide independent correctness references'),
        ('results/<category>/<batch>/<case>/actual.json; observations.json', 'Normalized answers and arrivals', 'Expose the conversion from output records to final groups'),
        ('results/<category>/<batch>/<case>/comparison.json', 'Per-case differences and sentinels', 'Determine whether group keys and amounts match'),
        ('results/latest-micro.json; latest-tpch.json', 'Latest functional batches', 'Select retained functional evidence'),
        ('results/summary.json; summary.csv', '28-case functional summary', 'Support correctness tables and coverage claims'),
        ('results/verifier-tests.json', 'Six comparator self-checks', 'Verify rejection of wrong amounts and wrong groups, plus normalization semantics'),
        ('results/latest-benchmark.json', 'Latest timing batch and summary', 'Supply report tables and plots'),
        ('results/benchmark/<batch>/runs.csv; summary.csv', 'Individual runs and configuration statistics', 'Separate warm-up, calculate medians/ranges and compare p=1/p=2'),
        ('logs/', 'Build, installation and execution logs', 'Preserve the process and failure evidence'),
        ('provenance/', 'Source hashes, environment and audits', 'Record implementation identity and distinguish original evidence from localization'),
        ('provenance/english-localization.json', 'Comment-translation and evidence identity record', 'Document changes while preserving executable code and original run evidence'),
        ('report/Cquirrel_Q3_Reproduction_Report.pdf; .docx', 'Final and editable English reports', 'Present all six required report topics and the expanded algorithm'),
        ('report/figures/runtime.png', 'Measured duration chart', 'Display medians and min/max ranges'),
        ('report/qa.json; rendered/final-*.png', 'Page checks and final renderings', 'Verify page count and visual quality'),
        ('report/reference/', 'English layout-reference extracts', 'Retain the supplied formatting example; not experimental evidence'),
        ('provenance/simple-repro-audit.json; simple-repro-manifest.json', 'Complete audit and current SHA-256 inventory', 'Identify the delivered version and its verification scope'),
    ]
    guide = ['# Files, purposes and roles in the reproduction', '',
             'Paths are relative to repro_final. Generated and vendor code originate from the official implementation; scripts provide the reproduction tooling.', '',
             '| File or directory | Purpose | Role in the reproduction |', '|---|---|---|']
    guide += ['| `{}` | {} | {} |'.format(*row) for row in mappings]
    (out / 'FILES.md').write_text('\n'.join(guide) + '\n', encoding='utf-8')
    print('ENGLISH_REPORTS_READY')

if __name__ == '__main__':
    write_report()
