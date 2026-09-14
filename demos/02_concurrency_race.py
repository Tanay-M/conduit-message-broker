import threading
import time

from _common import banner, check, done, fixtures, info, new_admin, new_client, step, timed

WORKERS = 3
TOTAL = 30

banner(f"DEMO 02 - CONCURRENCY: {WORKERS} consumers racing, SKIP LOCKED guarantees no double delivery")

admin = new_admin()
fx = fixtures(admin, "d2")
client = new_client(fx)
step(f"provisioned topic={fx['topic']} group={fx['group']}")

step(f"producing {TOTAL} unkeyed messages")
results, ms = timed(client.produce_batch, fx["topic"], [{"payload": {"event": "race", "n": i}} for i in range(TOTAL)], seq_start=1)
info(f"produced {len(results)} messages in {ms:.1f} ms")
check(len(results) == TOTAL, f"{TOTAL} messages produced")

step(f"starting {WORKERS} consumer threads simultaneously (threading.Barrier)")
barrier = threading.Barrier(WORKERS)
claimed = {i: [] for i in range(WORKERS)}
errors = []

def worker(i):
    try:
        barrier.wait()
        while True:
            batch = client.consume(fx["group"], fx["topic"], 10, 60)
            if not batch:
                break
            claimed[i].extend(m["location"] for m in batch)
    except Exception as e:
        errors.append(f"worker {i}: {e}")

threads = [threading.Thread(target=worker, args=(i,)) for i in range(WORKERS)]
start = time.perf_counter()
for t in threads:
    t.start()
for t in threads:
    t.join()
elapsed = time.perf_counter() - start

for e in errors:
    info(e)
check(not errors, "no worker raised an exception")

all_locations = [loc for locs in claimed.values() for loc in locs]
unique_locations = {(loc["partition_id"], loc["msg_offset"]) for loc in all_locations}

for i in range(WORKERS):
    info(f"worker {i} claimed {len(claimed[i])} messages")
info(f"drained the backlog in {elapsed * 1000:.1f} ms ({TOTAL / elapsed:.0f} msg/s)")

check(len(all_locations) == TOTAL, f"every message was claimed exactly once in total ({len(all_locations)}/{TOTAL})")
check(len(unique_locations) == TOTAL, f"no message was ever claimed by two workers ({len(unique_locations)} unique locations)")

step("acknowledging everything the three workers claimed")
client.ack(fx["group"], all_locations)
stats = admin.topic_stats(fx["topic"])
check(stats["delivered"] == TOTAL, f"all {TOTAL} messages delivered")

client.close()
admin.close()
done()
