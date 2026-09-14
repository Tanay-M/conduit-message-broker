import threading
import time

from _bench_common import banner, check, fixtures, new_admin, new_client, percentiles, print_table, save

BATCHES = [1, 10, 100, 1000]
TOTAL_PER_RUN = 2000
THREADS = 4
CONTEND_CALLS = 5
CONTEND_BATCH = 100

banner("BENCHMARK - PRODUCE: throughput + latency across batch sizes, then 4-producer contention")

admin = new_admin()
fx = fixtures(admin, "bp", schema={"required": ["event", "n"]})
client = new_client(fx)
print(f"  topic={fx['topic']} partitions=2 payload~=60B")

rows = []
n_counter = 0
seq = 1
for batch in BATCHES:
    calls = TOTAL_PER_RUN // batch
    samples = []
    t0 = time.perf_counter()
    for _ in range(calls):
        msgs = [{"payload": {"event": "bench", "n": n_counter + i}} for i in range(batch)]
        n_counter += batch
        t1 = time.perf_counter()
        client.produce_batch(fx["topic"], msgs, seq_start=seq)
        samples.append((time.perf_counter() - t1) * 1000)
        seq += batch
    elapsed = time.perf_counter() - t0
    rate = TOTAL_PER_RUN / elapsed
    rows.append(
        {
            "run": f"batch={batch}",
            "batch": batch,
            "calls": calls,
            "messages": TOTAL_PER_RUN,
            "msgs_per_s": round(rate, 1),
            "call_latency_ms": percentiles(samples),
        }
    )
    print(f"  batch={batch:>4}: {rate:>8.0f} msg/s over {calls} calls")

print(f"  contention run: {THREADS} concurrent producers, batch={CONTEND_BATCH}")
contend_base = seq
barrier = threading.Barrier(THREADS)
errors = []


def producer(tid):
    try:
        barrier.wait()
        for c in range(CONTEND_CALLS):
            msgs = [
                {"payload": {"event": "contend", "n": tid * 10_000 + c * CONTEND_BATCH + i}}
                for i in range(CONTEND_BATCH)
            ]
            client.produce_batch(
                fx["topic"], msgs, seq_start=contend_base + tid * 100_000 + c * CONTEND_BATCH
            )
    except Exception as e:
        errors.append(f"producer {tid}: {e}")


threads = [threading.Thread(target=producer, args=(i,)) for i in range(THREADS)]
t0 = time.perf_counter()
for t in threads:
    t.start()
for t in threads:
    t.join()
wall = time.perf_counter() - t0

for e in errors:
    print(f"     {e}")
check(not errors, "no producer raised an exception")

contend_msgs = THREADS * CONTEND_CALLS * CONTEND_BATCH
contend_rate = contend_msgs / wall
single_rate = next(r["msgs_per_s"] for r in rows if r["batch"] == CONTEND_BATCH)
rows.append(
    {
        "run": f"{THREADS}-producers batch={CONTEND_BATCH}",
        "batch": CONTEND_BATCH,
        "calls": THREADS * CONTEND_CALLS,
        "messages": contend_msgs,
        "msgs_per_s": round(contend_rate, 1),
        "speedup_vs_single": round(contend_rate / single_rate, 2),
    }
)
print(f"  {THREADS} producers: {contend_rate:.0f} msg/s (single-producer batch=100: {single_rate:.0f} msg/s)")

produced = admin.run(
    "SELECT count(*) AS n FROM message WHERE topic_id = %s::bigint", (fx["topic_id"],)
)[0]["n"]
expected = TOTAL_PER_RUN * len(BATCHES) + contend_msgs
check(produced == expected, f"message accounting: {produced}/{expected} rows on disk")

client.close()
save(
    "bench_produce",
    {"total_per_run": TOTAL_PER_RUN, "batch_sizes": BATCHES, "contention": {"threads": THREADS, "batch": CONTEND_BATCH}},
    rows,
)
print_table(
    "PRODUCE RESULTS",
    ["run", "msg/s", "p50 ms", "p95 ms", "p99 ms"],
    [
        [
            r["run"],
            r["msgs_per_s"],
            r["call_latency_ms"]["p50"],
            r["call_latency_ms"]["p95"],
            r["call_latency_ms"]["p99"],
        ]
        for r in rows
        if "call_latency_ms" in r
    ],
)
admin.close()
