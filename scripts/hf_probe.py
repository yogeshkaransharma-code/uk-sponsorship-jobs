from __future__ import annotations
import duckdb

db = duckdb.connect()
db.execute("SET http_timeout = 20000")
db.execute("SET threads = 2")
root = "hf://datasets/HeadcountLabs/job-postings/data"
tables = {
    "jobs": root + "/jobs/part-202610-*.parquet",
    "postings": root + "/postings/part-202610-*.parquet",
    "job_locations": root + "/job_locations/*.parquet",
}
for label,path in tables.items():
    try:
        result=db.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()
        print("COLUMNS",label,[(r[0],r[1]) for r in result],flush=True)
        rows=db.execute(f"SELECT * FROM read_parquet('{path}') LIMIT 2").fetchall()
        print("ROWS",label,[str(x)[:600] for x in rows],flush=True)
    except Exception as exc:
        print("ERROR",label,repr(exc)[:1500],flush=True)
try:
    num=db.execute(f"SELECT COUNT(DISTINCT job_id) FROM read_parquet('{tables['job_locations']}') WHERE country='GB'").fetchone()[0]
    print("UK_JOB_COUNT",num,flush=True)
except Exception as exc:
    print("UK_COUNT_ERROR",repr(exc)[:1500],flush=True)
