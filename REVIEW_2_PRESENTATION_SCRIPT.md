# Conduit — DBMS Project Review 2 Presentation & Defense Guide
**Criteria:** Second Review (Implementation Review) — **10 Marks**  
**Team 17:** G Anirudh (24BDS0335) · Tanay Mohta (24BDS0294) · Dhyey Dhumasia (24BCE0529)  
**PowerPoint File:** [`Conduit_DBMS_Review_2.pptx`](./Conduit_DBMS_Review_2.pptx)

---

## Evaluation Rubric Breakdown (10 Marks)

| Evaluation Component | Weight | Specific Conduit Artifacts |
|---|---|---|
| **1. Database Implementation** | 2.5 Marks | 15 tables in 3NF/BCNF, 157 constraints (composite PKs, FK ON DELETE, domain CHECKs), monthly range partitioning, JSONB schema validation. |
| **2. Data Insertion & Management** | 2.5 Marks | Idempotent 5-step produce transaction, 2,000-message production seed, per-topic `purge_retention()`, global floor partition drops, DLQ & reaper procedures. |
| **3. Database Operations** | 2.5 Marks | Non-blocking `SELECT ... FOR UPDATE SKIP LOCKED`, 4-table joins for consumer lag, single-pass `FILTER` aggregations, window functions for throughput. |
| **4. Advanced Database Features** | 2.5 Marks | PL/pgSQL procedures (`produce`, `consume`, `ack`, `nack`), 15 active triggers, native Row-Level Security (RLS) with `conduit_app` role, partial & BRIN indexes, materialized views, WAL recovery. |

---

## Slide-by-Slide Presentation Guide & Speaker Notes

### Slide 1: Title & Project Overview
- **Title:** CONDUIT: A Production-Grade Message Broker Built on PostgreSQL
- **Subtitle:** DBMS Project Review 2: Implementation Review (10 Marks)
- **Presenter:** Team 17
- **Core Thesis:** *"The DBMS is not an accessory to the broker — the DBMS IS the broker."*
- **Speaker Talking Points:**
  - Introduce the team and project.
  - State the core thesis: rather than using an external broker (Kafka/RabbitMQ) with a separate database causing dual-write synchronization bugs, modern PostgreSQL 16 contains all necessary database primitives to serve as a high-concurrency message broker natively.

---

### Slide 2: The Review 1 Pivot (Context & Evolution)
- **Title:** Context & Architectural Evolution: The Review 1 Pivot
- **Review 1 Problem:** The initial submission used a hybrid model where PostgreSQL only stored administrative metadata (6 tables: USER, TOPIC, etc.), while messages lived in custom files. This was rightly identified as "a distributed systems project with a database panel bolted on."
- **Review 2 Resolution:** We executed a complete pivot to a **100% RDBMS-core architecture**. Messages are relational rows; producing is an ACID transaction; consuming is `SELECT ... FOR UPDATE SKIP LOCKED`; durability is PostgreSQL's WAL.
- **Prior Art:** Backed by real-world production architectures: `pgmq`, `Message DB`, `graphile-worker`, and Quartz's JDBC store.

---

### Slide 3: Criterion 1 — Relational Schema Architecture (15 Tables)
- **Title:** Relational Schema Architecture: 15 Tables in 3NF / BCNF
- **Three Logical Tiers:**
  1. **Identity & Governance (4 Tables):**
     - `role`: Normalized role entities (`admin`, `operator`, `producer`, `consumer`, `viewer`).
     - `app_user`: System user accounts with status check (`active`, `suspended`).
     - `application`: Registered microservice clients with UUID API keys.
     - `access`: Fine-grained ACL grants on topics (`produce`, `consume`, `admin`).
  2. **Messaging Domain (5 Tables):**
     - `topic`: Topic metadata, retention window, and payload size bounds.
     - `partition`: Physical partitions with monotonic row-locked `next_offset`.
     - `schema_version`: Message contract validation definitions (JSONB).
     - `message`: The core table; monthly range-partitioned on `created_at`.
     - `producer_sequence`: Dedicated outbox deduplication ledger.
  3. **Consumption & Operations (6 Tables):**
     - `consumer_group`: Consumer group configuration and max retry limits.
     - `group_subscription`: $M:N$ junction table mapping groups to topics.
     - `group_offset`: Per-partition committed offset tracker.
     - `dead_letter_message`: Poison pill snapshot table.
     - `audit_log`: Append-only compliance trail populated exclusively by triggers.
     - `broker_config`: Dynamic key-value engine configuration.

---

### Slide 4: Criterion 1 — Constraints & Data Validation
- **Title:** Data Integrity: 157 Engine-Level Constraints & JSON Validation
- **Key Points:**
  - **157 Total Constraints** cataloged in `information_schema.table_constraints`.
  - **Composite Primary Keys:** `(created_at, topic_id, partition_id, msg_offset)` on `message`; `(producer_app_id, producer_seq)` on `producer_sequence`; `(group_id, topic_id)` on subscriptions; `(group_id, partition_id)` on offsets.
  - **Foreign Key Policies:** `ON DELETE RESTRICT` on topics/partitions to protect message integrity; `CASCADE` on group memberships; `SET NULL` on audit actors.
  - **Domain CHECK Constraints:** Status enums (`pending`, `claimed`, `delivered`, `dead`), offset bounds (`msg_offset >= 0`), retry thresholds (`1 <= max_delivery_attempts <= 10`), retention bounds (`1 <= retention_days <= 3650`).
  - **Dynamic In-Database JSON Schema Validation:** Stored function `fn_validate_schema(payload JSONB, schema JSONB)` validates message fields against `schema_version` definitions during the produce transaction. Invalid payloads raise exception `CDT04`.

---

### Slide 5: Criterion 1 — Physical Table Partitioning
- **Title:** Physical Database Design: Monthly Range Partitioning
- **Key Points:**
  - Native PostgreSQL 16 `PARTITION BY RANGE (created_at)` on the `message` table.
  - Partition tables: `message_2026_09` through `message_2027_03` plus `message_default`.
  - **Partition Pruning:** Time-based queries prune unneeded partition tables, eliminating full-table scans.
  - **PostgreSQL 16 FK Milestone:** In earlier PG versions, foreign keys referencing partitioned tables were restricted. In PG16, Conduit enforces 4 real foreign keys on `message` (topic, partition, app, consumer group).
  - **Split Retention Architecture:**
    - Per-topic purge: `purge_retention(topic_id)` issues a scoped `DELETE` honoring topic-level retention days.
    - Global floor drop: `drop_old_partitions(keep_days)` issues zero-downtime `ALTER TABLE DETACH PARTITION` and `DROP TABLE` for obsolete months.

---

### Slide 6: Criterion 2 — Data Insertion & Produce Pipeline
- **Title:** The Produce Transaction: 5-Step Atomic Ingestion Pipeline
- **Pipeline Workflow inside `produce()`:**
  1. `pg_advisory_xact_lock(app_id, seq)`: Serializes concurrent retries from the same client without table-level locks.
  2. **Idempotency Check:** Queries `producer_sequence`. Replayed sequences return original message coordinates with `is_duplicate = true` (zero double-inserts).
  3. **Hash Routing:** $\text{partition} = \text{abs}(\text{hashtext}(key)) \pmod N$ for consistent key routing; least-loaded round-robin for unkeyed messages.
  4. **Monotonic Offset Allocation:** `SELECT next_offset FROM partition FOR UPDATE`. Monotonically increments offset without gaps.
  5. **Insert & Notify:** Inserts into `message` and `producer_sequence`. Trigger fires `pg_notify('conduit_events', ...)` for real-time SSE.

---

### Slide 7: Criterion 2 — Dataset Seeding & Housekeeping
- **Title:** Dataset Seeding, Dead-Lettering & Housekeeping Procedures
- **Key Points:**
  - **The 2,000-Message Seed Dataset (`50_seed.sql`):** Gated by `CONDUIT_SEED=true`. Provisions an exact production distribution:
    - 1,580 Delivered (79%)
    - 390 Pending (19.5%)
    - 29 Claimed (1.45%)
    - 1 Dead letter message
  - **Dead Letter Queue (DLQ):** Messages exceeding `max_delivery_attempts` (default 3) are copied to `dead_letter_message` with failure reasons and marked `status = 'dead'`.
  - **Requeue Procedure (`requeue_dlq`):** Automatically republishes dead messages under a fresh sequence.
  - **Crashed Consumer Reaper (`reap_expired_claims`):** Automatically re-queues claimed messages whose visibility timeout expired (`visible_at <= now()`).

---

### Slide 8: Criterion 3 — Database Operations: The Consume Query
- **Title:** Operational Queries: Non-Blocking Consumption via SKIP LOCKED
- **The Core Query:**
  ```sql
  SELECT created_at, partition_id, msg_offset, payload, attempts
  FROM message
  WHERE topic_id = p_topic_id
    AND status = 'pending'
    AND (visible_at IS NULL OR visible_at <= now())
  ORDER BY msg_offset ASC
  LIMIT p_batch_size
  FOR UPDATE SKIP LOCKED;
  ```
- **Concurrency Mechanism:**
  - `FOR UPDATE` locks selected rows.
  - `SKIP LOCKED` instructs the engine to skip any rows currently locked by concurrent transactions.
  - Concurrency proof: Multiple worker processes drain the same partition concurrently with **zero lock waits and zero duplicate deliveries**.

---

### Slide 9: Criterion 3 — Joins, Aggregations & Window Functions
- **Title:** Complex Relational Joins, FILTER Aggregations & Window Functions
- **Key Points:**
  - **4-Table Join (`v_consumer_lag`):** Joins `consumer_group` $\bowtie$ `group_subscription` $\bowtie$ `partition` $\bowtie$ `group_offset` $\bowtie$ `topic` to dynamically compute:
    $$\text{lag} = \text{head\_offset} - \text{committed\_offset}$$
  - **Single-Pass Aggregations with `FILTER` (`v_topic_stats`):**
    ```sql
    count(*) FILTER (WHERE status = 'pending') AS pending,
    count(*) FILTER (WHERE status = 'delivered') AS delivered
    ```
    Computes all topic stats in a single table scan.
  - **SQL Window Functions (`v_throughput_by_minute`):** Uses `date_trunc('minute', created_at)` and `SUM(count(*)) OVER (ORDER BY minute)` for time-series throughput and running totals.

---

### Slide 10: Criterion 4 — Stored Procedures & Custom SQLSTATEs
- **Title:** Stored Procedures & Atomic Multi-Table Transactions
- **Key Points:**
  - Complete broker logic lives in PostgreSQL via `10_functions.sql`: `produce()`, `produce_batch()`, `consume()`, `ack()`, `nack()`, `reap_expired_claims()`, `requeue_dlq()`.
  - **Atomic Multi-Table Acknowledgment (`ack`):** Updates message `status = 'delivered'` AND advances `group_offset.committed_offset` inside the **same transaction**.
  - **Custom SQLSTATE Exception Codes (`CDT01`–`CDT21`):**
    - `CDT01`/`CDT02`: Unknown/inactive topic
    - `CDT04`: Schema contract validation failure
    - `CDT17`/`CDT18`: ACL produce/consume denial
    - `CDT19`: Monotonic offset regression rejection
    - `CDT21`: Suspended user access denial

---

### Slide 11: Criterion 4 — Active Database: 15 Triggers
- **Title:** Active Database Architecture: 15 Automated Triggers
- **Key Points:**
  - **Immutable Audit Triggers:** Fire `AFTER INSERT/UPDATE` on `message`, `dead_letter_message`, and `access` to write to `audit_log`. Bypassing audit is physically impossible.
  - **ACL Enforcement Triggers:** Fire `BEFORE INSERT/UPDATE` to verify producer/consumer permissions and active user status before touching data.
  - **Monotonic Offset Guard:** Fires `BEFORE UPDATE ON group_offset` to reject committed offset regression (`CDT19`).
  - **Real-Time Notification Trigger:** Fires `AFTER INSERT ON message` using `pg_notify('conduit_events', ...)` to drive Server-Sent Events (SSE) in the web UI.

---

### Slide 12: Criterion 4 — Row-Level Security (RLS)
- **Title:** Multi-Tenant Isolation via Native Row-Level Security (RLS)
- **Key Points:**
  - Dedicated non-superuser role: `conduit_app` (superuser bypasses RLS; dedicated role proves enforcement).
  - Session GUC identity injection: `SET LOCAL app.user_id = '<user_id>'`.
  - **5 Native RLS Policies:**
    - `message_select_policy`: Visible only if user holds `consume`, `produce`, or `admin` access.
    - `message_insert_policy`: Enforces produce access during write.
    - `message_update_policy`: Enforces consume access during state updates.
    - `dlq_select_policy` & `dlq_update_policy`.
  - **Security Invoker Views:** Views use `security_invoker = true` to inherit the caller's RLS permissions.

---

### Slide 13: Criterion 4 — Indexing Strategies & EXPLAIN Proofs
- **Title:** Engine Optimization: Partial Indexes, BRIN & EXPLAIN Proofs
- **Key Points:**
  - **Partial Index (`idx_message_pending`):** `ON message(...) WHERE status = 'pending'`. Indexes only unconsumed messages; remains fast even with millions of delivered rows.
  - **Reaper Partial Index (`idx_message_claimed_visible_at`):** `WHERE status = 'claimed'`. Scans only active in-flight claims.
  - **BRIN Index (Block Range Index):** On `message(created_at)` and `audit_log(event_timestamp)`. Stores block min/max values; $\approx 99\%$ smaller than B-Trees on append-only data.
  - **EXPLAIN at 30,000-Message Scale (`explain_at_scale.py`):** Proves the PostgreSQL planner chooses the partial pending index (bitmap scan, 1.9 ms execution, zero sequential scans).

---

### Slide 14: Criterion 4 — Materialized Views & Durability (WAL Recovery)
- **Title:** Materialized Views & WAL Crash Recovery Verification
- **Key Points:**
  - **Materialized View `mv_topic_stats`:** Caches aggregate metrics; refreshed via `REFRESH MATERIALIZED VIEW CONCURRENTLY` without read-blocking.
  - **Durability & Crash Recovery Proof (`08_wal_recovery.ps1`):**
    - 100 messages produced and acknowledged.
    - Host executes `docker kill -s 9 conduit-db` (SIGKILL hard crash).
    - Database restarts and triggers PostgreSQL automated WAL replay.
    - Result: All 100 acknowledged messages and committed offsets recover completely with **zero data loss**.

---

### Slide 15: Empirical Benchmarks & Defense Numbers
- **Title:** Production Benchmarks: Throughput, Concurrency & The Price of Guarantees
- **Key Metrics:**
  - **Produce Throughput:** 495 msg/s (batch 1) $\to$ 2,562 msg/s (batch 1000). Batching yields a $5\times$ to $15\times$ scale curve.
  - **Contention Resilience:** 4 concurrent producers contending on 2 partitions experience only a 7% throughput penalty (2,085 msg/s).
  - **Consume Throughput:** Up to 3,379 msg/s across 5 concurrent workers.
  - **The "Price of Guarantees" Defense (Milestone 8):**
    - Bare `INSERT` baseline: 106,183 msg/s ($1.0\times$)
    - `produce()` as Admin: 3,291 msg/s ($32.3\times$ overhead): Buys idempotency ledger, advisory locks, monotonic gap-free offsets, schema validation, audit triggers & NOTIFY.
    - `produce()` as App with RLS: 2,454 msg/s ($43.3\times$ overhead): RLS policy checks add $\approx 34\%$ on top of the admin path.

---

### Slide 16: System Demonstration & Tooling
- **Title:** Live Dashboard & Automated Scenario Verification
- **Key Points:**
  - **Web Dashboard (Port 8000):** Overview, Messages (live SSE), Playground, Topics, Groups, Audit, DLQ, and read-only SQL Console.
  - **8 Self-Asserting Demos (`demos/01`–`08`):**
    - `01_basic_flow.py`: Send $\to$ stored $\to$ read $\to$ ack.
    - `02_concurrency_race.py`: 3 racing consumers, zero duplicates.
    - `03_idempotency.py`: Retry storm deduplication.
    - `04_poison_dlq.py`: Poison message dead-lettering and requeue.
    - `05_crash_recovery.py`: Consumer crash and reaper recovery.
    - `06_security.py`: ACL & RLS enforcement.
    - `07_exactly_once.py`: Atomic ack and offset commit.
    - `08_wal_recovery.ps1`: SIGKILL crash and WAL replay.

---

### Slide 17: Conclusion & Rubric Saturation (10/10 Marks)
- **Title:** Conclusion: Review 2 Rubric Saturation
- **Comprehensive Scorecard Table:**
  - Database Implementation: 15 tables, 157 constraints, monthly range partitioning.
  - Data Insertion & Management: Idempotent produce transaction, 2,000-message seed, purge and reaper housekeeping.
  - Database Operations: Filtered scans, multi-table joins, single-pass aggregations, window functions.
  - Advanced Features: Stored procedures, 15 triggers, RLS, partial & BRIN indexes, materialized views, WAL recovery.

---

## Anticipated Review 2 Viva Questions & Model Answers

### Q1: "Why use PostgreSQL as a message broker when Kafka and RabbitMQ already exist?"
> **Model Answer:**  
> "Kafka and RabbitMQ excel at raw streaming throughput, but they introduce the classic dual-write problem when paired with a database. To keep database state and broker state consistent, applications either require complex two-phase commit (2PC) or CDC engines like Debezium. In Conduit, because messages are database rows, business data updates, message publication, and consumer offset commits happen inside a **single ACID transaction**. Furthermore, we leverage PostgreSQL's native features—WAL durability, row-level security, and audit triggers—without managing an external cluster."

### Q2: "Isn't a relational database too slow for a message queue?"
> **Model Answer:**  
> "Historically, RDBMS queues suffered because multiple consumers locked the entire table or caused deadlocks. Conduit eliminates this bottleneck using `SELECT ... FOR UPDATE SKIP LOCKED`, which allows workers to concurrently claim independent batches without waiting. Additionally, our partial index (`idx_message_pending`) indexes only unconsumed messages. In our Milestone 8 benchmarks, we demonstrated up to 3,379 consumes/sec and proven index scans in 1.9 ms across 30,000 messages."

### Q3: "How do you handle message deduplication?"
> **Model Answer:**  
> "We implement sequence-based idempotency using the `producer_sequence` ledger table. When a producer sends a message with an application sequence number, Conduit acquires a lightweight transaction-scoped advisory lock `pg_advisory_xact_lock(app_id, seq)` and checks the ledger. If the sequence was already ingested, it immediately returns the original message coordinates without inserting duplicates. This guarantees exactly-once message ingestion even during network retries."

### Q4: "Why is PRODUCER_SEQUENCE a separate table instead of a unique constraint on MESSAGE?"
> **Model Answer:**  
> "In PostgreSQL, any unique constraint on a partitioned table **must include the partition key** (`created_at`). If we put the unique constraint on `message(producer_app_id, producer_seq, created_at)`, a retry with a new timestamp would bypass the constraint and insert a duplicate. Creating a dedicated `producer_sequence` ledger with a composite primary key `(producer_app_id, producer_seq)` cleanly solves this constraint."
