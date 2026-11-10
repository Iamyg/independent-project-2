"""Small Q3 runtime experiment; every warm-up and measured run checks correctness."""
import csv
import datetime as dt
import json
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import time
import urllib.request
import duckdb
import experiment as e

ROOT=e.ROOT
CONFIG=json.loads((ROOT/'configs/benchmark.json').read_text())


def prepare(sf):
    folder=ROOT/'data/benchmark'/('sf'+str(sf))
    folder.mkdir(parents=True,exist_ok=True)
    database=folder/'tpch.duckdb'
    con=duckdb.connect(str(database))
    con.execute("LOAD '{}'".format(ROOT/'tools/duckdb-extensions/tpch.duckdb_extension'))
    if not con.execute('SHOW TABLES').fetchall():
        con.execute('CALL dbgen(sf={})'.format(sf))
    blocks={}
    for table,tag,order in [('customer','CU','c_custkey'),('orders','OR','o_orderkey'),('lineitem','LI','l_orderkey,l_linenumber')]:
        blocks[tag]=['+'+tag+'|'.join(map(str,row))+'|' for row in con.execute('SELECT * FROM {} ORDER BY {}'.format(table,order)).fetchall()]
    source=blocks['CU']+blocks['OR']+blocks['LI']
    deleted=blocks['LI'][::10]
    con.execute('CREATE OR REPLACE TEMP TABLE removed(l_orderkey BIGINT,l_linenumber INTEGER)')
    con.executemany('INSERT INTO removed VALUES (?,?)',[(int(x[3:].split('|')[0]),int(x[3:].split('|')[3])) for x in deleted])
    cases=[]
    for scenario in CONFIG['scenarios']:
        case_folder=folder/scenario
        case_folder.mkdir(exist_ok=True)
        events=source if scenario=='insert' else source+['-'+s[1:] for s in deleted]
        path=case_folder/'events.txt'
        path.write_text('\n'.join(events)+'\n')
        query=e.SQL if scenario=='insert' else 'WITH lineitem AS (SELECT l.* FROM main.lineitem l WHERE NOT EXISTS (SELECT 1 FROM removed d WHERE d.l_orderkey=l.l_orderkey AND d.l_linenumber=l.l_linenumber)) '+e.SQL
        answer=sorted([[int(k),str(date),int(priority),str(revenue)] for k,date,priority,revenue in con.execute(query).fetchall()])
        (case_folder/'reference.sql').write_text(query)
        e.save_json(case_folder/'reference.json',answer)
        case=dict(scale_factor=sf,scenario=scenario,input=str(path.relative_to(ROOT)),
                  input_events=len(events),insertions=len(source),deletions=0 if scenario=='insert' else len(deleted),
                  input_sha256=e.digest(path),expected_groups=len(answer))
        e.save_json(case_folder/'case.json',case)
        cases.append(case)
    e.save_json(folder/'generation.json',dict(duckdb=duckdb.__version__,scale_factor=sf,
              rows={k:len(v) for k,v in blocks.items()},delete_policy='Every tenth lineitem in (orderkey, linenumber) order',
              extension_sha256=e.digest(ROOT/'tools/duckdb-extensions/tpch.duckdb_extension')))
    con.close()
    print('DATA_READY',sf,{k:len(v) for k,v in blocks.items()},flush=True)
    return cases


def run_one(batch,case,p,warmup,repeat,index):
    name='{:02d}_sf{}_{}_p{}_{}_{}'.format(index,case['scale_factor'],case['scenario'],p,'warmup' if warmup else 'measure',repeat)
    out=batch/name
    out.mkdir()
    input_path=ROOT/case['input']
    expected=json.loads((input_path.parent/'reference.json').read_text())
    if e.digest(input_path)!=case['input_sha256']: raise ValueError('Changed input')
    start=time.perf_counter()
    log=e.command([Path(os.environ['FLINK_HOME'])/'bin/flink','run','-p',str(p),e.JAR,
                   '--input',input_path.as_uri(),'--output',(out/'raw-output').as_uri()],out/'flink.log',timeout=180)
    wall=time.perf_counter()-start
    job_id=re.findall(r'Job has been submitted with JobID ([0-9a-f]{32})',log)[0]
    with urllib.request.urlopen('http://127.0.0.1:8081/jobs/'+job_id,timeout=10) as response:
        job=json.load(response)
    e.save_json(out/'flink-job.json',job)
    if job['state']!='FINISHED': raise RuntimeError('Unfinished job')
    actual,observations,zero=e.normalize(out/'raw-output')
    diff=e.compare(expected,actual)
    e.save_json(out/'actual.json',actual)
    e.save_json(out/'comparison.json',dict(status='passed' if not diff else 'failed',expected_groups=len(expected),
                 actual_groups=len(actual),differences=diff,empty_group_sentinels=zero))
    effective=max(v['parallelism'] for v in job['vertices'])
    if effective!=p: raise RuntimeError('Requested parallelism was not applied')
    if diff: raise AssertionError('Incorrect result in '+name)
    result=dict(**case,parallelism=p,warmup=warmup,repeat=repeat,job_id=job_id,
                flink_duration_ms=job['duration'],client_wall_seconds=wall,output_records=len(observations),
                effective_max_parallelism=effective,status='passed',directory=str(out.relative_to(ROOT)),
                events_per_job_second=case['input_events']/(job['duration']/1000))
    e.save_json(out/'run.json',result)
    print(name,'PASS',job['duration'],'ms',flush=True)
    return result


def summarize(batch,rows):
    groups={}
    for row in rows:
        if not row['warmup']:
            groups.setdefault((row['scale_factor'],row['scenario'],row['parallelism']),[]).append(row)
    summary=[]
    for (sf,scenario,p),runs in sorted(groups.items()):
        durations=[r['flink_duration_ms'] for r in runs]
        median=statistics.median(durations)
        summary.append(dict(scale_factor=sf,scenario=scenario,parallelism=p,measured_runs=len(runs),
              input_events=runs[0]['input_events'],result_groups=runs[0]['expected_groups'],
              median_ms=median,min_ms=min(durations),max_ms=max(durations),
              median_events_per_job_second=runs[0]['input_events']/(median/1000),
              median_client_wall_seconds=statistics.median(r['client_wall_seconds'] for r in runs)))
    for row in summary:
        base=next(r for r in summary if r['scale_factor']==row['scale_factor'] and r['scenario']==row['scenario'] and r['parallelism']==1)
        row['speedup_vs_p1']=base['median_ms']/row['median_ms']
    for filename,content in [('runs.csv',rows),('summary.csv',summary)]:
        with (batch/filename).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(content[0]))
            writer.writeheader();writer.writerows(content)
    payload=dict(batch=str(batch.relative_to(ROOT)),config=CONFIG,runs=rows,summary=summary,
                 query_jar_sha256=e.digest(e.JAR),query_sql_sha256=e.digest(ROOT/'queries/q3.sql'))
    e.save_json(batch/'results.json',payload)
    e.save_json(ROOT/'results/latest-benchmark.json',payload)
    print('BENCHMARK_COMPLETE',len(rows),'validated jobs;',len(summary),'configurations',flush=True)


def main():
    e.ensure_flink()
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    batch=ROOT/'results/benchmark'/stamp
    batch.mkdir(parents=True)
    e.save_json(batch/'config.json',CONFIG)
    with (batch/'machine.txt').open('w') as stream:
        for args in [['uname','-a'],['lscpu'],['free','-h']]:
            subprocess.run(args,stdout=stream,stderr=subprocess.STDOUT,check=True)
    cases=[c for sf in CONFIG['scale_factors'] for c in prepare(sf)]
    combinations=[(case,p) for case in cases for p in CONFIG['parallelisms']]
    schedule=[]
    for case,p in combinations: schedule.append((case,p,True,0))
    rng=random.Random(CONFIG['shuffle_seed'])
    for repeat in range(1,CONFIG['measured_runs_per_configuration']+1):
        round_order=combinations[:];rng.shuffle(round_order)
        schedule.extend((case,p,False,repeat) for case,p in round_order)
    e.save_json(batch/'schedule.json',[dict(case=c,parallelism=p,warmup=w,repeat=n) for c,p,w,n in schedule])
    rows=[]
    for index,(case,p,warmup,repeat) in enumerate(schedule,1):
        rows.append(run_one(batch,case,p,warmup,repeat,index))
        e.save_json(batch/'progress.json',rows)
    summarize(batch,rows)


if __name__=='__main__': main()
