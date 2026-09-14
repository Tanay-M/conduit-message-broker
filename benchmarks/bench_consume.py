import threading
import time
import uuid

from _bench_common import banner, check, fixtures, new_admin, new_client, percentiles, print_table, save

BATCHES = [1, 10, 100, 1000]
TOTAL_PER_RUN = 2000
DRAIN_TOTAL = 5000
WORKERS = 5

banner("BENCHMARK - CONSUME: consume+ack throughput across batch sizes, then 5-worker drain")


def make_topic_group(admin, fx, tag):
    sfx = uuid.uuid4().hex[:8]
    topic = f"{tag}topic{sfx}"
    group = f"{tag}group{sfx}"
    topic_id = admin.create_topic(topic, 2, fx["user"], schema={"required": ["event", "n"]})
    admin.grant_access(fx["user"], topic, "produce", fx["user"])
    admin.grant_access(fx["user"], topic, "consume", fx["user"])
    admin.create_group(group, fx["user"])
    admin.subscribe_group(group, topic)
    return {"topic": topic, "topic_id": topic_id, "group": group}


admin = new_admin()
fx = fixtures(admin, "bc")
client = new_client(fx)

global_seq = 1


def produce_n(env, n):
    global global_seq
    client.produce_batch(
        env["topic"],
        [{"payload": {"event": "bench", "n": i}} for i in range(n)],
        seq_start=global_seq,
    )
    global_seq += n


rows = []
for batch in BATCHES:
    env = make_topic_group(admin, fx, f"bc{batch}")
    produce_n(env, TOTAL_PER_RUN)
    samples = []
    consumed = 0
    t0 = time.perf_counter()
    while True:
        t1 = time.perf_counter()
        msgs = client.consume(env["group"], env["topic"], batch, 120)
        if not msgs:
            break
        client.ack(env["group"], [m["location"] for m in msgs])
        samples.append((time.perf_counter() - t1) * 1000)
        consumed += len(msgs)
    elapsed = time.perf_counter() - t0
    rate = consumed / elapsed
    rows.append(
        {
            "run": f"batch={batch}",
            "batch": batch,
            "messages": consumed,
            "cycles": len(samples),
            "msgs_per_s": round(rate, 1),
            "cycle_latency_ms": percentiles(samples),
        }
    )
    print(f"  batch={batch:>4}: {rate:>8.0f} msg/s over {len(samples)} consume+ack cycles")
    check(consumed == TOTAL_PER_RUN, f"batch={batch}: drained exactly {TOTAL_PER_RUN}")

print(f"  drain race: {DRAIN_TOTAL} messages, 1 worker vs {WORKERS} workers (same group)")
single_env = make_topic_group(admin, fx, "bcs")
produce_n(single_env, DRAIN_TOTAL)
t0 = time.perf_counter()
drained = 0
while True:
    msgs = client.consume(single_env["group"], single_env["topic"], 100, 120)
    if not msgs:
        break
    client.ack(single_env["group"], [m["location"] for m in msgs])
    drained += len(msgs)
single_wall = time.perf_counter() - t0
single_rate = drained / single_wall
check(drained == DRAIN_TOTAL, f"single worker drained {DRAIN_TOTAL}")

multi_env = make_topic_group(admin, fx, "bcm")
produce_n(multi_env, DRAIN_TOTAL)
barrier = threading.Barrier(WORKERS)
errors = []
totals = {i: 0 for i in range(WORKERS)}


def worker(i):
    try:
        barrier.wait()
        while True:
            msgs = client.consume(multi_env["group"], multi_env["topic"], 100, 120)
            if not msgs:
                break
            client.ack(multi_env["group"], [m["location"] for m in msgs])
            totals[i] += len(msgs)
    except Exception as e:
        errors.append(f"worker {i}: {e}")


threads = [threading.Thread(target=worker, args=(i,)) for i in range(WORKERS)]
t0 = time.perf_counter()
for t in threads:
    t.start()
for t in threads:
    t.join()
multi_wall = time.perf_counter() - t0

for e in errors:
    print(f"     {e}")
check(not errors, "no worker raised an exception")

multi_drained = sum(totals.values())
multi_rate = multi_drained / multi_wall
check(multi_drained == DRAIN_TOTAL, f"{WORKERS} workers drained exactly {DRAIN_TOTAL}, no duplicates")

rows.append(
    {
        "run": f"1-worker drain (batch=100)",
        "messages": DRAIN_TOTAL,
        "wall_s": round(single_wall, 2),
        "msgs_per_s": round(single_rate, 1),
    }
)
rows.append(
    {
        "run": f"{WORKERS}-worker drain (batch=100)",
        "messages": DRAIN_TOTAL,
        "wall_s": round(multi_wall, 2),
        "msgs_per_s": round(multi_rate, 1),
        "speedup_vs_single": round(multi_rate / single_rate, 2),
    }
)
print(f"  1 worker:  {single_rate:.0f} msg/s ({single_wall:.2f}s)")
print(f"  {WORKERS} workers: {multi_rate:.0f} msg/s ({multi_wall:.2f}s) -> speedup {multi_rate / single_rate:.2f}x")

client.close()
save(
    "bench_consume",
    {"total_per_run": TOTAL_PER_RUN, "batch_sizes": BATCHES, "drain_total": DRAIN_TOTAL, "workers": WORKERS},
    rows,
)
print_table(
    "CONSUME RESULTS",
    ["run", "msg/s", "p50 ms", "p95 ms"],
    [
        [r["run"], r["msgs_per_s"], r["cycle_latency_ms"]["p50"], r["cycle_latency_ms"]["p95"]]
        for r in rows
        if "cycle_latency_ms" in r
    ],
)
admin.close()
