import json
import time

from _bench_common import banner, check, fixtures, new_admin, new_client, percentiles, print_table, save

ROWS_PER_CALL = 1000
CALLS = 20

banner("BENCHMARK - PRICE OF GUARANTEES: raw insert vs produce-as-admin vs produce-as-app (RLS)")

admin = new_admin()
fx = fixtures(admin, "bo", schema={"required": ["event", "n"]})
client = new_client(fx)
print(f"  {ROWS_PER_CALL} rows per call x {CALLS} calls per tier, identical ~60B payloads")

admin.run("DROP TABLE IF EXISTS bench_raw_message")
admin.run(
    "CREATE TABLE bench_raw_message ("
    "created_at TIMESTAMPTZ NOT NULL DEFAULT now(), topic_id BIGINT, partition_id BIGINT, "
    "msg_offset BIGINT, msg_key TEXT, payload JSONB, size_bytes INT, producer_app_id BIGINT, "
    "producer_seq BIGINT, status VARCHAR(16) NOT NULL DEFAULT 'pending', claimed_by BIGINT, "
    "visible_at TIMESTAMPTZ, attempts INT NOT NULL DEFAULT 0)"
)

raw_sql = (
    "INSERT INTO bench_raw_message (topic_id, partition_id, msg_offset, msg_key, payload, "
    "size_bytes, producer_app_id, producer_seq) "
    "SELECT %s::bigint, %s::bigint, g, 'bench-' || g, jsonb_build_object('event','bench','n',g), "
    "64, %s::bigint, g FROM generate_series(%s::int, %s::int) g"
)
partition_id = admin.run(
    "SELECT pt.partition_id FROM partition pt WHERE pt.topic_id = %s::bigint ORDER BY pt.partition_id LIMIT 1",
    (fx["topic_id"],),
)[0]["partition_id"]

tiers = []


def measure(name, call):
    samples = []
    t0 = time.perf_counter()
    for i in range(CALLS):
        t1 = time.perf_counter()
        call(i)
        samples.append((time.perf_counter() - t1) * 1000)
    wall = time.perf_counter() - t0
    rate = (ROWS_PER_CALL * CALLS) / wall
    tiers.append(
        {
            "tier": name,
            "messages": ROWS_PER_CALL * CALLS,
            "msgs_per_s": round(rate, 1),
            "call_latency_ms": percentiles(samples),
        }
    )
    print(f"  {name:<28}: {rate:>8.0f} msg/s  (p50 {percentiles(samples)['p50']:.0f} ms/call)")


print("  tier 1: bare INSERT into an unguarded table (baseline)")
measure("raw insert (no guarantees)", lambda i: admin.run(
    raw_sql,
    (fx["topic_id"], partition_id, fx["app"]["app_id"], i * ROWS_PER_CALL + 1, (i + 1) * ROWS_PER_CALL),
))

print("  tier 2: produce() as admin - advisory lock, idempotency ledger, offset assignment, triggers, NOTIFY")
admin_msgs = [
    json.dumps(
        [{"seq": 100_000 + i * ROWS_PER_CALL + j, "payload": {"event": "bench", "n": i * ROWS_PER_CALL + j}}
         for j in range(ROWS_PER_CALL)]
    )
    for i in range(CALLS)
]
measure("produce() as admin", lambda i: admin.run(
    "SELECT * FROM produce_batch(%s::text, %s::jsonb, %s::bigint)",
    (fx["topic"], admin_msgs[i], fx["app"]["app_id"]),
))

print("  tier 3: produce() as conduit_app - same + RLS policy evaluation per row")
client_msgs = [
    [{"payload": {"event": "bench", "n": i * ROWS_PER_CALL + j}} for j in range(ROWS_PER_CALL)]
    for i in range(CALLS)
]
measure("produce() as conduit_app (RLS)", lambda i: client.produce_batch(
    fx["topic"], client_msgs[i], seq_start=200_000 + i * ROWS_PER_CALL
))

raw_count = admin.run("SELECT count(*) AS n FROM bench_raw_message")[0]["n"]
broker_count = admin.run(
    "SELECT count(*) AS n FROM message WHERE topic_id = %s::bigint", (fx["topic_id"],)
)[0]["n"]
check(raw_count == ROWS_PER_CALL * CALLS, f"raw tier inserted {raw_count} rows")
check(broker_count == ROWS_PER_CALL * CALLS * 2, f"broker tiers produced {broker_count} messages")

admin.run("DROP TABLE bench_raw_message")

raw_rate = tiers[0]["msgs_per_s"]
for t in tiers:
    t["overhead_factor_vs_raw"] = round(raw_rate / t["msgs_per_s"], 2)
print(f"  overhead vs raw: admin path {tiers[1]['overhead_factor_vs_raw']}x, app+RLS path {tiers[2]['overhead_factor_vs_raw']}x")

client.close()
save("bench_overhead", {"rows_per_call": ROWS_PER_CALL, "calls": CALLS}, tiers)
print_table(
    "PRICE OF GUARANTEES",
    ["tier", "msg/s", "p50 ms", "p95 ms", "overhead x"],
    [
        [t["tier"], t["msgs_per_s"], t["call_latency_ms"]["p50"], t["call_latency_ms"]["p95"], t["overhead_factor_vs_raw"]]
        for t in tiers
    ],
)
admin.close()
