# Real application options and Review 2 evidence plan

Research date: 13 October 2026. This is a proposal, not a description of an implemented application. No broker schema, queries, application code, or presentation deck were changed for this research.

Update 17 October 2026: the user selected **report generation** as the preferred direction and supplied updated final PPT/report guidelines plus a 20-mark allocation. The current recommendation and implementation proposal are in [REPORTING_PROJECT_BLUEPRINT.md](REPORTING_PROJECT_BLUEPRINT.md). The comparisons below retain the earlier research context.

## Recommendation

Use **Conduit for asynchronous e-commerce order fulfilment preparation**. A small storefront accepts an order; Conduit stores a fulfilment job; a separately controlled warehouse worker generates a real downloadable packing slip and records completion. This makes the broker's purpose understandable while retaining a strong relational database story.

The best alternative is **photo upload and thumbnail processing**: the audience sees the original and the actual resized output. **Business report exports** and **support-ticket processing** are two further credible choices. These rankings are engineering judgments about this project and its assessment, not measured implementation estimates.

Keep Conduit as the DBMS-backed message broker. The selected application is its demonstration client. The broker currently has 15 logical tables, SQL functions, triggers, views, indexes, and transactional operations; an application does not need to replace them or add tables merely to increase a count. The assessment supplies no mandatory table count and lists advanced features as applicable.

## 1. E-commerce fulfilment preparation

### Why this is a real application

Shopify documents order-management and fulfilment applications as integrations with merchant order and shipping workflows. Separately, its webhook guidance explicitly recommends queuing incoming work for asynchronous processing and handling repeated deliveries idempotently. These sources establish the real use case; our local demonstration would not be a Shopify integration. [Shopify orders and fulfilment](https://shopify.dev/docs/apps/build/orders-fulfillment), [Shopify webhook delivery guidance](https://shopify.dev/docs/apps/build/webhooks/verify-deliveries).

### Smallest useful demonstration

Seed a fictional customer and a catalogue of three products. Use an order form with product, quantity, and address. Treat payment as outside the demonstration boundary, with orders already accepted for processing. On submission, create an order and enqueue one job on `order-fulfilment`. The warehouse worker reads the order lines, computes totals, generates an HTML/PDF packing slip, records its result, and acknowledges the message. The user can open the actual file.

Proposed flow: order form -> accepted order plus Conduit job -> warehouse worker -> packing slip and completion record.

Conduit does the job storage, claiming, duplicate-producer handling, retries, dead-letter storage, and broker audit. The worker performs the application work. A simulated carrier outage can be a labelled failure control, but the packing-slip generation should be real. Producing a slip means fulfilment preparation completed; it does not mean a parcel was physically shipped.

Suggested business records, subject to final design: `customer`, `product`, `sales_order`, `order_item`, and `fulfilment_result`. Useful constraints include foreign keys, positive quantity, nonnegative prices, allowed order states, and one completion result per job/order as the workflow requires. Store the sale-time price on an order line if the catalogue price can change. Add only the relationships needed by the agreed flow.

Natural database questions: Which accepted orders are still waiting? Which customer owns this job? What are the items and total for this order? How many jobs succeeded or failed? Which failures were retried? Order values belong to the order records, not a sum of every broker retry/message, which would overcount.

Failure examples: a valid-shaped job referencing an unavailable order reaches the worker and fails; an input missing a required message field is rejected before insertion. Keep these separate. A paused worker demonstrates queuing. Two workers demonstrate separate claims. Repeating the same producer identity demonstrates ingress deduplication; a unique result key and appropriate transaction design would additionally be needed to prevent duplicate worker effects.

### Scope boundary

One queue and one fulfilment worker pool are enough. A full cart, real payments, shipping API, refunds, distributed stock reservation, and several services consuming independent copies of one event would considerably enlarge the project. The current broker uses shared message status across groups; it does not implement independent subscriber-group fan-out. Microsoft distinguishes competing consumers from publish/subscribe explicitly. [Microsoft competing consumers](https://learn.microsoft.com/en-us/azure/architecture/patterns/competing-consumers).

Do not claim that saving an order and publishing a message are already atomic together. We must implement both using the same database transaction/connection or a deliberate outbox design after scenario selection. The existing `produce()` transaction covers its broker changes, not an order insert on an unrelated connection.

## 2. Photo upload and thumbnail processing

An upload portal stores an image and submits a processing job; a worker creates a thumbnail or resized image. AWS provides an official Lambda/S3 thumbnail-generation tutorial demonstrating this actual class of background processing. We would use Conduit and local files instead of requiring AWS. [AWS thumbnail tutorial](https://docs.aws.amazon.com/lambda/latest/dg/with-s3-tutorial.html).

Minimum demonstration: upload one photo while the worker is stopped, show its pending job, start the worker, and display original and thumbnail side by side. Submit a short batch for two workers. A labelled corrupt image passes the job's JSON shape validation but fails image decoding and eventually appears in the DLQ.

Proposed records: image asset and generated variant, linked to an owner and job identifier. Natural constraints are unique asset ID, foreign keys, positive target dimensions, allowed formats, and unique `(asset_id, variant_name)` for results. Keep image bytes in files; store references and metadata in PostgreSQL, with JSON messages carrying the asset/job identity.

Queries: pending assets by owner; asset-to-result LEFT JOIN to find missing thumbnails; counts by format and processing state; input/output byte totals and compression ratio. These make the database criteria concrete even though the most visible effect is an image transformation.

This is the easiest visually convincing option. It needs image and file handling, and completion/file consistency must be designed deliberately. It has less naturally rich business data than order fulfilment unless asset/result records are modelled properly.

## 3. Business report export service

A manager requests a sales, stock, or expense report; the request becomes a background job; a worker executes joins and aggregations and produces a downloadable CSV/report. Microsoft's Power BI ExportToFile API uses asynchronous export jobs, status checks, and file retrieval, establishing that deferred report generation is a real product workflow. A local version would have no Power BI dependency. [Power BI export workflow](https://learn.microsoft.com/en-us/power-bi/developer/embedded/export-to).

Minimum demonstration: seed fictional business records, request a report for a date range, show the queued request, run the worker, and open the generated CSV. Submit separate report requests to competing workers. Invalid date ranges should be rejected at input; a valid-shaped request for an unavailable report template can exercise worker failure/DLQ.

Proposed records: existing business data plus report request/result records. Constraints include valid date ranges, foreign keys to requester/template where used, allowed format/status, and result uniqueness. Queries naturally demonstrate date filtering, joins, GROUP BY, SUM/COUNT, HAVING, and views. Distinguish the generated report's business aggregates from broker operational metrics.

This option exposes SQL most directly. To justify the queue in a small demo, show independently submitted report jobs and worker unavailability; any added delay should be labelled a demonstration delay rather than a performance measurement.

## 4. Customer support ticket processing

A customer submits a support ticket; Conduit queues classification/routing work; a worker assigns a department/agent according to explicit rules and writes a visible case summary. Zendesk's official documentation describes asynchronous ticket creation through a queued job/status flow, including triggers and database writes. [Zendesk asynchronous ticket creation](https://developer.zendesk.com/documentation/ticketing/managing-tickets/improving-performance-by-creating-tickets-asynchronously/).

Minimum demonstration: submit a billing or technical ticket; show it awaiting processing; start the worker; show its actual assigned agent and generated summary. A well-formed ticket for an unavailable routing department fails in the worker. Pause the pool and submit several tickets, then recover it.

Proposed records: customer, ticket, department, agent, and assignment/result as needed. Natural constraints include foreign keys, allowed priorities/states, required subject, and one current assignment per ticket. Queries include tickets by priority/status, ticket-customer-agent joins, counts by department, and unresolved tickets above a chosen age threshold.

This is familiar, but a tiny instantaneous routing rule alone gives a weaker reason for background processing. Demonstrate buffering/recovery and a real persisted outcome. Avoid requiring an external AI classifier or real email for the core demo. Notification sending can be a separately labelled extension.

## Comparison

| Option | Visible result | Natural relational evidence | Local demo effort | Main consideration |
|---|---|---|---|---|
| Order fulfilment preparation | Packing slip plus completed job/order | Very strong: customer/order/item/product/result | Moderate | Keep the scope around fulfilment preparation |
| Photo processing | Original and thumbnail | Good: asset/owner/variant/job | Low to moderate | Make metadata relations and SQL evidence visible |
| Report exports | Downloadable report built from business rows | Very strong: joins, date filters, sums, groups | Low to moderate | Explain why reports run independently in workers |
| Support ticket processing | Assigned ticket and case summary | Strong: customer/ticket/department/agent | Moderate | Simple routing needs a clear queue/recovery demonstration |

These are relative estimates for a small demonstration, not delivery promises. All can run locally without a paid external service.

## How to show the five Review 2 criteria

For each claim, show **an action, its SQL/definition, its actual result, and the reason the database feature matters**. This is a proposed presentation method grounded in the assessment, not a separate institutional requirement. Official PostgreSQL documentation supplies the feature semantics below; it does not prescribe the review's marks.

| Assessment category | What faculty should see | Concrete evidence |
|---|---|---|
| Tables and constraints/validation | Compact ER diagram plus valid and invalid examples | Actual DDL/catalog definitions; a FK/CHECK/UNIQUE rejection; required-field rejection through `produce()` |
| Insertion and management | Submit, process, pause/resume, retry/requeue | Stored message and ledger rows; actual status changes; DLQ management; a selected config update |
| Queries, filtering, aggregation, joins | Useful questions answered by SQL | Pending-work WHERE query; message-topic-application-user JOIN; counts GROUP BY/FILTER; optional business totals |
| Advanced features | One observable example of each selected feature | Function call, trigger-written audit, view query, transaction rollback, index definition/query plan, competing claims |
| Presentation | One request traced from input to tangible output | Architecture, readable SQL/result pairs, before/after screens, rubric evidence matrix |

PostgreSQL constraints reject invalid relational values; routine-level JSON validation is a separate mechanism. Conduit's current `validate_schema()` checks object shape and required keys, not the full JSON Schema specification. Domain checks such as quantities/dimensions must therefore be implemented explicitly where required. [PostgreSQL constraints](https://www.postgresql.org/docs/16/ddl-constraints.html).

The current source uses stored **functions**, not CREATE PROCEDURE routines. The rubric says advanced features are applicable examples, so do not add a procedure solely to rename an existing function. Demonstrate the functions already doing the work.

## Readable SQL examples using the current broker schema

These SELECT statements are derived from the inspected source. `orders` exists in the supplied seed; the selected application's topic name would replace it later. This report does not claim a fresh execution of these individual snippets. The broader existing [evidence script](../demos/review_2_evidence.sql) was executed successfully during [runtime verification](RUNTIME_VERIFICATION.md).

### Filtering and meaningful joins

Question: Which pending order messages exist, which application submitted them, and who owns that application?

```sql
SELECT m.payload ->> 'order_id' AS order_id,
       t.topic_name, a.app_name, u.username,
       m.status, m.attempts, m.created_at
FROM message m
JOIN topic t ON t.topic_id = m.topic_id
JOIN application a ON a.app_id = m.producer_app_id
JOIN app_user u ON u.user_id = a.owner_user_id
WHERE t.topic_name = 'orders' AND m.status = 'pending'
ORDER BY m.created_at DESC
LIMIT 10;
```

Point at WHERE for filtering and JOIN/ON for relationships, then show the returned rows. The order ID here is a payload field, not proof that a relational order table exists. Add the business-table join only after its schema is implemented. [PostgreSQL joins](https://www.postgresql.org/docs/16/tutorial-join.html).

### Aggregation

Question: How many messages are in each processing state?

```sql
SELECT t.topic_name, m.status, count(*) AS messages
FROM message m
JOIN topic t ON t.topic_id = m.topic_id
WHERE t.topic_name = 'orders'
GROUP BY t.topic_name, m.status
ORDER BY m.status;
```

Submit or finish a job, rerun the query, and explain the changed counts. Counts describe message rows, not unique orders or completed shipments. [PostgreSQL aggregate functions](https://www.postgresql.org/docs/16/tutorial-agg.html).

### View

```sql
SELECT topic_name, pending, claimed, delivered, dead, dlq_pending
FROM v_topic_stats
WHERE topic_name = 'orders';
```

Show the view's definition beside its output. Its grouping and status counts are in `db/sql/40_views.sql`. A view presents a reusable database query; the existing materialized view is a separate feature requiring refresh and should not be described as automatically current. [PostgreSQL views](https://www.postgresql.org/docs/16/tutorial-views.html).

### Trigger-written audit

```sql
SELECT topic_name, event_type, status, details, event_timestamp
FROM v_audit_recent
WHERE topic_name = 'orders'
  AND event_type IN ('PRODUCE', 'DELIVERED', 'DLQ')
ORDER BY event_timestamp DESC, log_id DESC
LIMIT 10;
```

After submitting a controlled job, show its PRODUCE audit entry and the definition of `message_insert_audit`. After worker completion, show DELIVERED and `message_delivered_audit`. Neither action needs a manual audit INSERT. Actual trigger definitions are in `db/sql/20_triggers.sql`. Correlate a selected job by its partition/offset details and job key instead of implying every audit entry already contains an order ID. [PostgreSQL trigger functions](https://www.postgresql.org/docs/16/plpgsql-trigger.html).

### Constraints from the actual database

```sql
SELECT conrelid::regclass AS relation, conname,
       pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid IN ('public.message'::regclass,
                   'public.producer_sequence'::regclass,
                   'public.group_subscription'::regclass)
ORDER BY conrelid::regclass::text, conname;
```

For a live negative test, use a disposable demo fixture: negative producer sequence (CHECK), nonexistent application reference (FK), repeated ledger identity (PK), and missing required payload key through `produce()` (routine validation). Do not use direct invalid inserts into real data as a review preparation shortcut. Use an explicit transaction/savepoint and roll back the test. A rejection alone is not enough: also show that no invalid row persisted.

### Transaction evidence

The present `produce()` updates the partition counter, inserts the message and producer ledger, and invokes the insert audit trigger in the caller's transaction. In an isolated prepared fixture, snapshot those rows/counter, invoke a two-job `produce_batch()` containing a valid job followed by one with a missing required field, observe the error, roll back the failed transaction, and show that none of the first job's changes persisted. This is a proposed proof to prepare and verify, not a newly executed result. Transactions provide all-or-nothing database changes; they do not automatically make file generation or a remote service atomic. [PostgreSQL transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html).

### Indexing and concurrency

Show the partial pending index definition from `00_schema.sql`, then EXPLAIN a SELECT with the matching topic/status predicate. If timing is needed, use EXPLAIN (ANALYZE, BUFFERS) only on a read-only query. PostgreSQL may correctly choose a sequential scan on a tiny dataset; prepare a separate representative dataset if index-use evidence is needed. Do not force an index and call that proof of a speedup. [PostgreSQL EXPLAIN](https://www.postgresql.org/docs/16/using-explain.html), [examining index usage](https://www.postgresql.org/docs/16/indexes-examine.html).

For concurrency, use two real worker connections and show distinct claimed job identities. Then display the `FOR UPDATE SKIP LOCKED` selection inside `consume()`. It skips row locks held by other transactions and is explicitly suitable for queue-like consumers; it does not mean lock-free processing. [PostgreSQL SELECT locking](https://www.postgresql.org/docs/16/sql-select.html).

## Proposed presentation arrangement

Use three visible areas: application input/output, Conduit queue/worker status, and a read-only database evidence panel or separate SQL client. For each step label the business question and DBMS concept, display a short query/definition, and show its live result. A database panel is a proposed addition, not an existing feature. Use curated read-only queries rather than arbitrary privileged SQL execution exposed to users.

First explain one job using the application. Then show the ER slice and SQL evidence. A complete 15-table ER diagram can be an appendix while the main diagram highlights the relationships used by that job. No normal app action needs to depend on faculty entering SQL.

Suggested eight-minute flow: one-minute context and architecture; two minutes submit with worker paused then produce actual output; one minute constraints and duplicate submission; two minutes joins, counts, view, and trigger audit; one minute rollback/index/concurrency evidence; one minute rubric matrix and questions. Recovery/DLQ can replace an advanced-feature step or be a prepared supplementary demonstration if time is short.

Use an evidence checklist with columns: requirement, exact file/query, demo action, expected result, observed result, verified/not yet verified. Never prefill observed results or predict full marks. Capture readable results/screenshots as backups for the eventual PPT.

## Before implementation

Choose one scenario, output, and boundary. Then fix the confirmed runtime defects in [RUNTIME_VERIFICATION.md](RUNTIME_VERIFICATION.md), add the minimum producer-worker-output workflow, implement its required domain constraints and result idempotency, and verify the precise rubric evidence. For e-commerce, address the order-plus-enqueue transaction explicitly. Prepare a reproducible isolated dataset and failures. Build the deck after the working evidence exists.

Avoid presenting the currently faulty dashboard count, offset-derived lag under out-of-order acknowledgement, or DLQ access path as verified correct features. Permission demonstrations should use the intended access path and corrected implementation; current RLS-related caveats remain documented in the runtime/readiness reports.

Further primary-source notes for the three alternatives: [ALTERNATIVE_DEMO_RESEARCH.md](ALTERNATIVE_DEMO_RESEARCH.md).
