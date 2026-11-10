# Cquirrel Q3 simple reproduction

This English package contains the same executable query, datasets and measured evidence as the companion `repro` directory. Documentation, report text, filenames and explanatory comments are in English. Translation does not represent additional experiment runs.

The query follows Section 2 of the paper: `AUTOMOBILE`, with the date boundary `1995-03-13`. It returns all qualifying revenue groups without ORDER BY or LIMIT. Independent DuckDB SQL checks final answers; small scenarios also have hand-calculated answers.

The current report uses the original paper title, **Cquirrel: Continuous Query Processing over Acyclic Relational Schemas**.

## Deliverables and results

- `report/Cquirrel_Q3_Reproduction_Report.pdf`: seven-page English report, including the expanded algorithm description.
- `report/Cquirrel_Q3_Reproduction_Report.docx`: editable version of the same report.
- `report/FILES.md`: artifact roles and their contribution to the reproduction.
- `results/summary.json`: 28 functional cases, all passed.
- `results/latest-benchmark.json`: 32 validated timing runs: eight warm-ups and 24 measured runs across eight configurations.

The report covers background and related work, query and algorithm, implementation, setup and datasets, results and discussion, and future directions. The algorithm explanation includes live-state conditions, keyed indexes, insertion/deletion propagation, the aggregate update equation and a worked example.

## Running the experiments

From Windows PowerShell in `D:\Learning\HKUST\ip`:

```powershell
.\repro_final\run.ps1 all
.\repro_final\run.ps1 benchmark
```

Individual stages:

```powershell
.\repro_final\run.ps1 prepare       # Create 22 small scenarios and hand answers
.\repro_final\run.ps1 build         # SQL -> JSON -> Scala -> JAR
.\repro_final\run.ps1 test          # Verify that incorrect answers are rejected
.\repro_final\run.ps1 micro         # Replay all small scenarios
.\repro_final\run.ps1 tpch          # Generate/read SF=0.001 and run six scenarios
.\repro_final\run.ps1 report        # Refresh English Markdown summaries
```

Equivalent WSL invocation:

```bash
bash /mnt/d/Learning/HKUST/ip/repro_final/scripts/repro.sh all
```

The existing runtime is loaded from `/home/chai_guanpeng/cquirrel-repro/activate.sh`: Java, Maven, Flink, Python and the shared Maven cache remain there. The English entry point derives its own root, so new experiment inputs and outputs go under `repro_final`. Flink service working files remain in the existing Flink installation. `bootstrap` is a dependency preparation entry point; retained source, CodeGen JAR, DuckDB wheel and signed TPC-H extension are already available.

Each rerun creates a new timestamped results directory. The copied historical logs retain original execution paths and JobIDs; those paths are evidence of the original runs, not instructions to write into the companion directory. `latest-micro.json`, `latest-tpch.json` and `latest-benchmark.json` select the latest corresponding batch.

## Method and implementation boundaries

1. Pin official release commit `501cfde6dc2968cfccee992ab4f298c499cc8028` and use the original core JAR.
2. Parse `queries/q3.sql`, retain the JSON plan, generate Scala operators and build the executable JAR.
3. Retain untouched generated code in `generated/original`; expose input/output argument and text-format changes in `patches/job-cli-output.patch`. Relation and aggregation algorithms are unchanged.
4. Start each functional scenario from empty state and compare answers after Flink reports FINISHED. Lifecycle prefixes are separate jobs; intermediate output order is not assumed to match input-event order.
5. Replay functional inputs into primary-key dictionaries, reject duplicate insertions/invalid deletions and execute the final SQL in DuckDB with DECIMAL amounts.
6. Normalize aggregate outputs by retaining the last arriving value per group. Outputs contain updated revenue, not additive deltas; source event numbers cannot reorder them.
7. Require identical group keys and amount error at most `max(1e-6, 1e-9 * abs(reference))`.

The adapted output is `order key|order date|shipping priority|updated revenue|source event number`. Removing a group's last contribution may emit zero or a tiny residual. Because every tested contribution is strictly positive, final absolute revenue at most `1e-6` is treated as an empty-group sentinel and recorded separately. This does not support arbitrary zero/negative contributions or cancellation.

The official parser matches aggregate names case-sensitively. Uppercase `SUM` can omit aggregation metadata and code generation may print an exception yet return a successful exit code. The query uses equivalent lowercase `sum`, with explicit plan/file/JAR checks. Failed-plan and failure-log evidence is preserved.

## Timing experiment and interpretation

`configs/benchmark.json` fixes SF=0.001/0.01, p=1/2, insertion and insertion followed by deletion of approximately 10% of line items. Each of eight configurations has one warm-up and three measured runs. Configuration order is shuffled within each measured round using seed 20261023. Every run also validates correctness and effective parallelism.

The archived batch is `results/benchmark/20261023T083453979792Z`. `runs.csv` stores individual runs; `summary.csv` stores medians, ranges and speedups. Each run retains Flink REST details, logs, raw output and comparison results. Primary time is Flink job duration, including deployment, input, operators and file output. Client wall time is stored separately.

No p=2 configuration has a lower median than its p=1 counterpart. This small single-machine experiment uses one TaskManager and serial file source/sink. It does not establish distributed scalability, per-update latency, fault recovery or performance relative to another system. The paper's larger Q5 scaling experiment is outside this reproduction.

## Report generation and verification

`scripts/create_final_report.py` reads archived JSON and creates the figure and Word report. It requires a Windows Python with python-docx/reportlab and Poppler; the authoring script locates the bundled Codex dependency runtime. `scripts/export_report.ps1` exports the report through a separate hidden Microsoft Word instance. Poppler renders pages for visual review. `scripts/audit_final_artifacts.py` checks archived jobs, recomputes statistics, compares report tables and writes the final checksum inventory.

`run.ps1 report` refreshes English Markdown summaries only. After new measurements, rebuild the Word/PDF report and review its discussion and pages. The narrative describes this archived experiment and must be reconsidered if configurations change.

`report/RESULTS.md` and `provenance/final-audit.json` describe the initial functional stage. `provenance/simple-repro-audit.json` audits the complete simple reproduction. Earlier manifests remain historical records; `provenance/simple-repro-manifest.json` indexes the current English package.

## Source localization

Six Chinese comments in the copied upstream `Parser.java` are translated into English. Executable Java tokens, all query/operator code, data and JARs are unchanged. `provenance/english-localization.json` records original and translated hashes; the original upstream manifest still describes the unmodified source revision. Licenses are retained. The authors' implementation is not claimed as an original algorithm of this project.

## Sources

- [Cquirrel paper](https://www.cse.ust.hk/~yike/Cquirrel.pdf)
- [Pinned release source](https://github.com/hkustDB/Cquirrel-release/tree/501cfde6dc2968cfccee992ab4f298c499cc8028)
- [Core aggregate output semantics](https://github.com/hkustDB/Cquirrel-core-release/blob/main/src/main/scala/org/hkust/BasedProcessFunctions/AggregateProcessFunction.scala)
- [DuckDB TPC-H extension](https://duckdb.org/docs/stable/core_extensions/tpch)
- [DuckDB 1.1.3](https://pypi.org/project/duckdb/1.1.3/)
