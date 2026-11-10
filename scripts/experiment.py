"""Reproducible bounded-stream Q3 experiments; artifacts stay under repro/."""
import csv
import datetime as dt
import difflib
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / 'configs/experiment.json').read_text())
VENDOR = ROOT / 'vendor/Cquirrel-release'
SQL = (ROOT / 'queries/q3.sql').read_text()
JAR = ROOT / 'generated/generated-code/target/generated-code-1.0-SNAPSHOT-jar-with-dependencies.jar'
ABS = Decimal(CFG['absolute_tolerance'])
REL = Decimal(CFG['relative_tolerance'])


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, log, timeout=600, cwd=ROOT):
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w') as stream:
        stream.write('COMMAND: ' + json.dumps([str(a) for a in args]) + '\n')
        stream.flush()
        result = subprocess.run([str(a) for a in args], cwd=str(cwd), stdout=stream,
                                stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed; see ' + str(log))
    return log.read_text(errors='replace')


def event(tag, values, sign='+'):
    return sign + tag + '|'.join(map(str, values)) + '|'


def customer(key=1, segment='AUTOMOBILE'):
    return event('CU', [key, 'Customer#' + str(key), 'Address', 0, '00-000', '0.00', segment, 'fixture'])


def order(key=101, customer_key=1, date='1995-03-01'):
    return event('OR', [key, customer_key, 'O', '1500.00', date, '1-URGENT', 'Clerk#1', 0, 'fixture'])


def line(number=1, price='1000.00', discount='0.10', date='1995-03-20', order_key=101):
    return event('LI', [order_key, 1, 1, number, '1.00', price, discount, '0.00', 'N', 'O',
                        date, '1995-03-10', '1995-03-25', 'DELIVER IN PERSON', 'AIR', 'fixture'])


def remove(value):
    assert value.startswith('+')
    return '-' + value[1:]


def write_case(name, events, expected=None, description='', category='micro'):
    folder = ROOT / 'data' / category / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'events.txt'
    path.write_text('\n'.join(events) + '\n')
    meta = dict(name=name, category=category, events=len(events), input_sha256=digest(path),
                description=description, expected=expected)
    save_json(folder / 'case.json', meta)
    return meta


def prepare_micro():
    c, o, a, b = customer(), order(), line(), line(2, '500.00', '0.20')
    seq = [c, o, a, b, remove(a), remove(c), c]
    cases = []
    for name, n, revenue in [('01_no_detail', 2, None), ('02_one_detail', 3, '900'),
                             ('03_two_details', 4, '1300'), ('04_delete_detail', 5, '400'),
                             ('05_delete_customer', 6, None), ('06_restore_customer', 7, '400')]:
        expected = [] if revenue is None else [[101, '1995-03-01', 0, revenue]]
        cases.append(write_case(name, seq[:n], expected, 'Independent replay of lifecycle prefix.'))
    extras = [
        ('07_delete_order', [c,o,a,b,remove(o)], []),
        ('08_restore_order', [c,o,a,b,remove(o),o], [[101,'1995-03-01',0,'1300']]),
        ('09_delete_last_detail', [c,o,a,remove(a)], []),
        ('10_late_parents', [a,b,o,c], [[101,'1995-03-01',0,'1300']]),
        ('11_wrong_segment', [customer(segment='BUILDING'),o,a], []),
        ('12_order_date_boundary', [c,order(date='1995-03-13'),a], []),
        ('13_ship_date_boundary', [c,o,line(date='1995-03-13')], []),
        ('14_future_order', [c,order(date='1995-03-14'),a], []),
        ('15_early_shipment', [c,o,line(date='1995-03-12')], []),
        ('16_missing_customer', [o,a,b], []),
        ('17_missing_order', [c,a,b], []),
        ('18_two_orders', [c,o,order(102),a,line(order_key=102)],
         [[101,'1995-03-01',0,'900'],[102,'1995-03-01',0,'900']]),
        ('19_delete_filtered_detail', [c,o,a,line(2,date='1995-03-13'),remove(line(2,date='1995-03-13'))],
         [[101,'1995-03-01',0,'900']]),
        ('20_delete_reinsert_detail', [c,o,a,remove(a),a], [[101,'1995-03-01',0,'900']]),
        ('21_update_discount', [c,o,a,remove(a),line(discount='0.25')], [[101,'1995-03-01',0,'750']]),
        ('22_change_customer_segment', [c,o,a,remove(c),customer(segment='BUILDING')], []),
    ]
    cases += [write_case(name, events, expected) for name, events, expected in extras]
    save_json(ROOT / 'data/micro/manifest.json', cases)
    print('Prepared', len(cases), 'micro cases.', flush=True)


def build():
    (ROOT / 'generated').mkdir(exist_ok=True)
    log = command(['java','-jar',ROOT / 'tools/codegen-1.0-SNAPSHOT.jar',
                   '-q',SQL,'-j',ROOT / 'queries/q3.generated.json','-g',ROOT / 'generated',
                   '-i',(ROOT / 'data/micro/03_two_details/events.txt').as_uri(),
                   '-o',(ROOT / 'tmp/default-output.txt').as_uri(),'-s','file'],
                  ROOT / 'logs/codegen.log', timeout=1200)
    project = ROOT / 'generated/generated-code'
    if not (project / 'pom.xml').exists():
        raise RuntimeError('Code generation did not produce a POM; see logs/codegen.log')
    # Keep the exact generator output before our CLI/output-format adaptation.
    archive = ROOT / 'generated/original'
    archive.mkdir(exist_ok=True)
    shutil.copy2(project / 'pom.xml', archive / 'pom.xml')
    shutil.copytree(project / 'src', archive / 'src', dirs_exist_ok=True)
    job = project / 'src/main/scala/org/hkust/Job.scala'
    before = job.read_text()
    after = re.sub(r'val inputpath = "[^"]*"', 'val inputpath = params.getRequired("input")', before)
    after = re.sub(r'val outputpath = "[^"]*"', 'val outputpath = params.getRequired("output")', after)
    # Preserve all operator output fields; dates are canonical and independent of locale.
    mapped = '.map(x => x._4.map { case d: java.util.Date => new java.text.SimpleDateFormat("yyyy-MM-dd").format(d); case v => v.toString }.mkString("|") + "|" + x._6)'
    after, count = re.subn(r'(?m)^\s*\.map\(x => .*$', '      ' + mapped, after)
    if count != 1 or after == before:
        raise RuntimeError('Unexpected generated Job layout; inspect before adapting')
    after = after.replace('env.execute("Flink Streaming Scala API Skeleton")',
                          'env.execute("Cquirrel Q3 reproduction")')
    job.write_text(after)
    (ROOT / 'patches/job-cli-output.patch').write_text(''.join(difflib.unified_diff(
        before.splitlines(True),after.splitlines(True),fromfile='original/Job.scala',tofile='generated/Job.scala')))
    command(['mvn','-B','-f',project / 'pom.xml','-DskipTests','package'],
            ROOT / 'logs/generated-build.log', timeout=1200)
    if not JAR.exists():
        raise RuntimeError('Missing compiled query JAR')
    save_json(ROOT / 'provenance/build.json', dict(query_sha256=digest(ROOT / 'queries/q3.sql'),
              jar_sha256=digest(JAR), core_sha256=digest(VENDOR / 'cquirrel-core-1.0-SNAPSHOT.jar'),
              codegen_sha256=digest(ROOT / 'tools/codegen-1.0-SNAPSHOT.jar'),
              generated_files=[str(p.relative_to(ROOT)) for p in project.glob('src/**/*.scala')]))
    print('QUERY_BUILD_OK', flush=True)


def prepare_tpch():
    import duckdb
    folder = ROOT / 'data/tpch/source'
    folder.mkdir(parents=True, exist_ok=True)
    extension_dir = ROOT / 'tools/duckdb-extensions'
    extension_dir.mkdir(parents=True, exist_ok=True)
    database = folder / 'tpch.duckdb'
    con = duckdb.connect(str(database))
    platform = con.execute('PRAGMA platform').fetchone()[0]
    extension = extension_dir / 'tpch.duckdb_extension'
    url = 'https://extensions.duckdb.org/v{}/{}/tpch.duckdb_extension.gz'.format(duckdb.__version__, platform)
    if not extension.exists():
        packed = extension.with_suffix('.gz')
        command(['curl','-fL','--retry','2','--connect-timeout','20','--max-time','180','-o',packed,url],
                ROOT / 'logs/tpch-extension-download.log', timeout=600)
        extension.write_bytes(gzip.decompress(packed.read_bytes()))
    # DuckDB checks its official extension signature on LOAD.
    con.execute("LOAD '{}'".format(str(extension).replace("'","''")))
    existing = {r[0] for r in con.execute('SHOW TABLES').fetchall()}
    metadata = folder / 'generation.json'
    if existing and metadata.exists():
        previous = json.loads(metadata.read_text())
        if previous['scale_factor'] != CFG['tpch_scale_factor'] or previous['duckdb_version'] != duckdb.__version__:
            con.close()
            raise ValueError('Existing TPC-H data uses a different scale/version; archive it before changing configuration')
    if not existing:
        con.execute('CALL dbgen(sf={})'.format(CFG['tpch_scale_factor']))
    blocks = {}
    for table, tag, ordering in [('customer','CU','c_custkey'),('orders','OR','o_orderkey'),
                                 ('lineitem','LI','l_orderkey,l_linenumber')]:
        rows = con.execute('SELECT * FROM {} ORDER BY {}'.format(table,ordering)).fetchall()
        text = ['|'.join(map(str,row)) + '|' for row in rows]
        (folder / (table+'.tbl')).write_text('\n'.join(text)+'\n')
        blocks[tag] = ['+'+tag+row for row in text]
    baseline = con.execute(SQL).fetchall()
    if not baseline:
        raise RuntimeError('Generated TPC-H has no qualifying Q3 groups; adjust data scale')
    chosen_order = int(sorted(baseline)[0][0])
    chosen_customer = con.execute('SELECT o_custkey FROM orders WHERE o_orderkey=?',[chosen_order]).fetchone()[0]
    c = next(x for x in blocks['CU'] if int(x[3:].split('|')[0]) == chosen_customer)
    o = next(x for x in blocks['OR'] if int(x[3:].split('|')[0]) == chosen_order)
    qualifying_lines = con.execute("SELECT l_orderkey,l_linenumber FROM lineitem WHERE l_orderkey=? AND l_shipdate>DATE '1995-03-13' ORDER BY l_linenumber",[chosen_order]).fetchall()
    keys = set(qualifying_lines)
    affected = [x for x in blocks['LI'] if (int(x[3:].split('|')[0]),int(x[3:].split('|')[3])) in keys]
    full = blocks['CU'] + blocks['OR'] + blocks['LI']
    scenarios = [
        ('insert',full),
        ('delete_lineitems',full+[remove(x) for x in affected]),
        ('delete_order',full+[remove(o)]),
        ('delete_customer',full+[remove(c)]),
        ('mixed_restore',full+[remove(c)]+[remove(x) for x in affected]+[c]),
        ('late_parents',blocks['LI']+blocks['OR']+blocks['CU']),
    ]
    cases = [write_case(name,events,category='tpch',description='TPC-H SF='+str(CFG['tpch_scale_factor']))
             for name,events in scenarios]
    save_json(ROOT / 'data/tpch/manifest.json',cases)
    save_json(folder / 'generation.json', dict(generator='DuckDB official signed tpch extension',
             duckdb_version=duckdb.__version__, extension_url=url, extension_sha256=digest(extension),
             scale_factor=CFG['tpch_scale_factor'], table_rows={k:len(v) for k,v in blocks.items()},
             initial_q3_groups=len(baseline), chosen_order=chosen_order, chosen_customer=chosen_customer,
             files={p.name:digest(p) for p in folder.glob('*.tbl')}))
    con.close()
    print('TPC-H_READY', {k:len(v) for k,v in blocks.items()}, 'Q3 groups:', len(baseline), flush=True)


def reference(input_path, output_dir):
    import duckdb
    tables = {'CU':{},'OR':{},'LI':{}}
    counts = {'insert':0,'delete':0}
    for number, raw in enumerate(Path(input_path).read_text().splitlines(),1):
        sign, tag = raw[0], raw[1:3]
        cells = raw[3:].rstrip('|').split('|')
        if tag not in tables or sign not in '+-':
            raise ValueError('Invalid event at line '+str(number))
        if len(cells) != {'CU':8,'OR':9,'LI':16}[tag]:
            raise ValueError('Unexpected column count at line '+str(number))
        key = (int(cells[0]),int(cells[3])) if tag=='LI' else int(cells[0])
        table = tables[tag]
        if sign == '+':
            if key in table:
                raise ValueError('Duplicate primary key at line '+str(number))
            table[key] = cells
            counts['insert'] += 1
        else:
            if table.get(key) != cells:
                raise ValueError('Delete must match existing row at line '+str(number))
            del table[key]
            counts['delete'] += 1
    con = duckdb.connect(str(output_dir / 'reference.duckdb'))
    con.execute('CREATE TABLE customer(c_custkey BIGINT,c_mktsegment VARCHAR)')
    con.execute('CREATE TABLE orders(o_orderkey BIGINT,o_custkey BIGINT,o_orderdate DATE,o_shippriority INTEGER)')
    con.execute('CREATE TABLE lineitem(l_orderkey BIGINT,l_linenumber INTEGER,l_extendedprice DECIMAL(18,2),l_discount DECIMAL(4,2),l_shipdate DATE)')
    projected = {
        'customer':[(int(c[0]),c[6]) for c in tables['CU'].values()],
        'orders':[(int(c[0]),int(c[1]),c[4],int(c[7])) for c in tables['OR'].values()],
        'lineitem':[(int(c[0]),int(c[3]),Decimal(c[5]),Decimal(c[6]),c[10]) for c in tables['LI'].values()]}
    for table,rows in projected.items():
        if rows:
            con.executemany('INSERT INTO {} VALUES ({})'.format(table,','.join('?' for _ in rows[0])),rows)
    rows = con.execute(SQL).fetchall()
    results = sorted([[int(k),str(date),int(priority),str(revenue)] for k,date,priority,revenue in rows])
    # Positive contributions make a zero output an unambiguous empty-group sentinel for this experiment.
    positive = con.execute('SELECT COUNT(*) FROM lineitem WHERE l_extendedprice<=0 OR l_discount>=1 OR l_discount<0').fetchone()[0] == 0
    if not positive:
        raise ValueError('This result adapter requires strictly positive line contributions')
    con.close()
    save_json(output_dir / 'reference.json',results)
    return results, counts


def normalize(path):
    path = Path(path)
    files = sorted(p for p in path.rglob('*') if p.is_file() and not p.name.startswith('.')) if path.is_dir() else [path]
    state, observations = {}, []
    for file in files:
        for row in file.read_text().splitlines():
            fields = row.strip().split('|')
            if len(fields) != 5:
                raise ValueError('Unexpected output row: '+row)
            k,date,priority,value,source_sequence = fields
            key = (int(k),date,int(priority))
            amount = Decimal(value)
            if not amount.is_finite():
                raise ValueError('Non-finite amount')
            state[key] = amount
            observations.append(dict(key=list(key),revenue=str(amount),source_sequence=int(source_sequence)))
    # One sink, preserved per-key arrival order. Source sequence is NOT an output ordering key.
    zero = [list(k)+[str(v)] for k,v in sorted(state.items()) if abs(v)<=ABS]
    rows = [list(k)+[str(v)] for k,v in sorted(state.items()) if abs(v)>ABS]
    return rows, observations, zero


def compare(expected, actual):
    exp = {tuple(r[:3]):Decimal(r[3]) for r in expected}
    act = {tuple(r[:3]):Decimal(r[3]) for r in actual}
    diffs=[]
    for key in sorted(exp.keys() | act.keys()):
        if key not in exp or key not in act:
            diffs.append(dict(key=key,expected=exp.get(key),actual=act.get(key)))
        elif abs(exp[key]-act[key]) > max(ABS,REL*abs(exp[key])):
            diffs.append(dict(key=key,expected=exp[key],actual=act[key],error=act[key]-exp[key]))
    return diffs


def ensure_flink():
    command(['bash',ROOT.parent / 'setup/cquirrel.sh','start'], ROOT / 'logs/flink-start.log',timeout=120)


def run_case(category, case, batch):
    folder = ROOT / 'data' / category / case['name']
    output = batch / case['name']
    output.mkdir(parents=True, exist_ok=False)
    input_path = folder / 'events.txt'
    if digest(input_path) != case['input_sha256']:
        raise ValueError('Input hash differs from case manifest')
    expected, counts = reference(input_path, output)
    if case['expected'] is not None and compare(case['expected'],expected):
        raise AssertionError('SQL reference differs from hand-calculated fixture')
    started = time.perf_counter()
    log = command([Path(os.environ['FLINK_HOME'])/'bin/flink','run','-p',str(CFG['parallelism']),
                   JAR,'--input',input_path.as_uri(),'--output',(output/'raw-output').as_uri()],
                  output / 'flink.log',timeout=180)
    elapsed = time.perf_counter()-started
    ids = re.findall(r'Job (?:has been submitted with JobID|with JobID) ([0-9a-f]{32})',log)
    if not ids:
        raise RuntimeError('No Flink JobID in '+str(output))
    job_id = ids[-1]
    with urllib.request.urlopen('http://127.0.0.1:8081/jobs/'+job_id,timeout=10) as response:
        job = json.load(response)
    save_json(output/'flink-job.json',job)
    if job['state'] != 'FINISHED':
        raise RuntimeError('Flink job not FINISHED')
    actual, observations, zeros = normalize(output/'raw-output')
    save_json(output/'actual.json',actual)
    save_json(output/'observations.json',observations)
    differences = compare(expected,actual)
    maximum_error = max([abs(Decimal(a[3])-Decimal(e[3])) for a,e in zip(actual,expected)
                         if a[:3]==e[:3]] or [Decimal(0)])
    result = dict(name=case['name'],category=category,status='passed' if not differences else 'failed',
                  job_id=job_id, input_sha256=digest(input_path),input_events=case['events'],**counts,
                  expected_groups=len(expected),actual_groups=len(actual),output_records=len(observations),
                  empty_group_sentinels=zeros,differences=differences,max_absolute_error=maximum_error,
                  parallelism=CFG['parallelism'],client_wall_seconds=elapsed,
                  flink_duration_ms=job['duration'],query_jar_sha256=digest(JAR))
    save_json(output/'comparison.json',result)
    print(category+'/'+case['name'], result['status'], 'groups',len(actual),'events',case['events'],flush=True)
    return result


def run_suite(category):
    ensure_flink()
    manifest=json.loads((ROOT/'data'/category/'manifest.json').read_text())
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    batch=ROOT/'results'/category/stamp
    batch.mkdir(parents=True)
    save_json(batch/'config.json',CFG)
    results=[]
    for case in manifest:
        try:
            results.append(run_case(category,case,batch))
        except Exception as error:
            results.append(dict(name=case['name'],category=category,status='error',error=str(error)))
            save_json(batch/case['name']/'error.json',results[-1])
            print('ERROR',case['name'],error,flush=True)
        save_json(batch/'summary.json',results)
    save_json(ROOT/'results'/('latest-'+category+'.json'),dict(batch=str(batch.relative_to(ROOT)),results=results))
    if any(r['status']!='passed' for r in results):
        raise RuntimeError('Some '+category+' cases failed; see '+str(batch))
    print(category.upper()+'_SUITE_PASSED',len(results),flush=True)


def test_verifier():
    from tempfile import TemporaryDirectory
    assert compare([[1,'1995-01-01',0,'10']], [[1,'1995-01-01',0,'11']])
    assert compare([[1,'1995-01-01',0,'10']], [])
    assert compare([], [[1,'1995-01-01',0,'10']])
    assert not compare([[1,'1995-01-01',0,'10']], [[1,'1995-01-01',0,'10.00000001']])
    with TemporaryDirectory(dir=ROOT/'tmp') as tmp:
        p=Path(tmp)/'output'
        p.write_text('1|1995-01-01|0|900|3\n1|1995-01-01|0|1300|4\n1|1995-01-01|0|400|2\n')
        rows,_,_=normalize(p)
        assert rows==[[1,'1995-01-01',0,'400']], 'Use arrival order, not source timestamp or sum'
        p.write_text('1|1995-01-01|0|900|3\n1|1995-01-01|0|0.0|4\n')
        assert normalize(p)[0]==[]
    save_json(ROOT/'results/verifier-tests.json',dict(status='passed',checks=6,
              checks_description=['wrong amount','missing key','extra key','float tolerance','snapshot arrival order','zero sentinel']))
    print('VERIFIER_TESTS_PASSED',flush=True)


def report():
    combined=[]
    for category in ['micro','tpch']:
        path=ROOT/'results'/('latest-'+category+'.json')
        if path.exists():
            combined.extend(json.loads(path.read_text())['results'])
    save_json(ROOT/'results/summary.json',dict(total=len(combined),passed=sum(r['status']=='passed' for r in combined),cases=combined))
    keys=['category','name','status','input_events','insert','delete','expected_groups','actual_groups',
          'output_records','flink_duration_ms','client_wall_seconds','max_absolute_error','job_id']
    with (ROOT/'results/summary.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=keys,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(combined)
    print('REPORT_SUMMARY',len(combined),'cases',flush=True)
    from write_report import write_report
    write_report()


if __name__=='__main__':
    action=sys.argv[1] if len(sys.argv)>1 else 'all'
    if action=='prepare': prepare_micro()
    elif action=='prepare-tpch': prepare_tpch()
    elif action=='build': build()
    elif action=='micro': run_suite('micro')
    elif action=='tpch': prepare_tpch(); run_suite('tpch')
    elif action=='report': report()
    elif action=='test': test_verifier()
    elif action=='all':
        prepare_micro(); build(); test_verifier(); run_suite('micro'); prepare_tpch(); run_suite('tpch'); report()
    else: raise SystemExit('Unknown action: '+action)
