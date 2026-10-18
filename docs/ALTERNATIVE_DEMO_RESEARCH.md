# Real application alternatives for Conduit's Review 2 demo

Research date: 13 October 2026. This supplements `DEMO_SCENARIO_RESEARCH.md` with three options outside e-commerce and campus document requests. These are proposed demonstration applications. No proposed business tables, workers, interfaces, or queries below have been implemented by this research.

## Recommendation and project boundary

For the most immediately understandable visual result, choose **photo upload and thumbnail processing**. For the strongest natural explanation of joins and aggregation, choose **asynchronous business report generation**. For a familiar operational workflow, choose **customer support ticket intake and routing**. All three can run locally with fictional fixtures and produce real outputs, without cloud accounts or external API credentials.

Conduit remains the PostgreSQL-backed message broker. The scenario supplies a producer, a worker, and an observable result. Use one topic and one worker group with two worker processes. Current Conduit uses shared message delivery state: different groups do not each get a copy of every message. Independent worker jobs fit this implementation. Microsoft's competing-consumers documentation distinguishes workers sharing jobs from publish-subscribe subscribers each receiving an event. This is the appropriate architectural comparison, not a promise that Conduit inherits another service's guarantees. [Microsoft competing consumers](https://learn.microsoft.com/en-us/azure/architecture/patterns/competing-consumers).

The relative strengths below are engineering judgments, not published measurements or grading promises.

| Proposed application | Visible completed work | Most natural DBMS evidence | Consideration |
|---|---|---|---|
| Photo upload and processing | Original beside a real thumbnail, plus dimensions and file size | Asset-to-owner/result joins, status and transformation aggregates | A metadata schema alone is smaller than an order/report domain; use the existing broker schema for advanced evidence |
| Business reports/export jobs | Downloadable CSV with totals checked against SQL | Date filtering, joins, GROUP BY, SUM, HAVING, views | Explain why background processing matters for large exports; a tiny fixture is intentionally a reduced demonstration |
| Support ticket intake/routing | Ticket assigned to the appropriate support team, visible worklist and recorded result | Customer/ticket/team joins, open workload and category counts | Simple routing may be fast; queue buffering and recovery are the purpose, not a fabricated expensive algorithm |

## 1. Photo upload and thumbnail processing

### Real-world grounding

AWS's official tutorial implements image upload triggering a function that resizes the image and writes a thumbnail. It directly establishes the real file-processing use case. It does not require Conduit to use S3 or Lambda; our proposed local queue substitutes for the trigger/worker infrastructure. [AWS thumbnail tutorial](https://docs.aws.amazon.com/lambda/latest/dg/with-s3-tutorial.html).

Microsoft also identifies uploaded-image thumbnail generation as work suitable for a background job, so the user need not wait for completion. [Microsoft background-job guidance](https://learn.microsoft.com/en-us/azure/architecture/best-practices/background-jobs).

### Small proposed demo

A photography or media portal accepts JPG/PNG uploads. The portal saves the original to controlled local storage and submits `asset_id` and a transformation version to an `image-jobs` topic. A separate Python worker uses an image library to generate a fixed-size thumbnail and stores output metadata. The portal displays the original, pending badge, thumbnail, and recorded dimensions after success.

Keep bytes in local files and relational metadata in PostgreSQL; the queue payload references the asset ID rather than embedding image bytes. Thumbnail generation must actually happen. An artificial delay, if used to make queue states observable, must be labelled as a demonstration delay.

Proposed supporting entities: asset owner (reuse an appropriate existing user identity where possible), `media_asset`, and `media_result`. Useful constraints include owner FK, positive file size and dimensions, permitted format/status values, and a unique `(asset_id, transformation_version)` result identity. That last constraint supports repeat-safe result publication; it is not a claim of end-to-end exactly-once execution.

### Faculty-visible success and failure

1. Stop workers and upload three files. Originals exist and jobs are pending; thumbnails do not yet exist.
2. Start two workers. Show them claiming different jobs, then open the actual thumbnails.
3. Show a JOIN returning owner, original filename, output dimensions, and job status.
4. Submit a valid job that references a stored file whose bytes are corrupt. The worker fails decoding, retries, and eventually reaches DLQ.
5. Replace the corrupt source with a valid image and requeue; the thumbnail now appears.

An HTTP upload rejected before a message is inserted demonstrates intake validation, not worker retry or DLQ. File disappearance/corruption after intake is a clear processing failure. Use separate fixtures for these two proofs.

### Natural Review 2 examples

| Criterion | Proposed visible proof |
|---|---|
| Tables/constraints/validation | ER slice of asset -> owner/result; attempt an unknown owner FK or invalid dimensions and show rejection |
| Insertion/management | Upload inserts metadata and queued job; worker updates status and inserts the result; operator retries failed work |
| Queries/filtering/aggregation/joins | Failed assets from today; owner/asset/result JOIN; count jobs by status; SUM original and result bytes to calculate actual space savings for fixtures |
| Advanced features | Existing produce/consume functions; audit triggers; `v_topic_stats`; pending partial index; transactions and two-worker claiming |
| Presentation | Upload -> stored job -> worker -> real thumbnail; show SQL and changed rows for the same asset ID |

## 2. Customer support ticket intake and routing

### Real-world grounding

Zendesk documents asynchronous ticket creation: its API can queue a creation job, return a ticket/job identifier, and expose queued, working, failed, and completed states. It explains that processing includes triggers and database persistence. This supports a real ticket-workflow use case. Our proposed deterministic team-routing rules are our own reduced demonstration, not a claim about Zendesk's implementation. [Zendesk asynchronous ticket creation](https://developer.zendesk.com/documentation/ticketing/managing-tickets/improving-performance-by-creating-tickets-asynchronously/).

### Small proposed demo

A customer submits “Cannot log in,” selecting the account-access category. Intake creates a submission and enqueues a routing job. A worker reads database routing rules, creates/updates the ticket with the correct team, and records a result visible in that team's worklist. Three categories and two or three teams are enough; no AI classification, email delivery, or full helpdesk product is required.

Proposed supporting entities: `customer`, `support_team`, `ticket`, and `routing_rule`, using only those necessary for the final design. Useful constraints include customer/team FKs, required subject, permitted priority/status values, unique submission reference, and one active route per category. A ticket requiring team assignment should have a real assignment/result shown, rather than simply turning a queue badge green.

### Faculty-visible success and failure

Stop workers, submit several support requests, and show that intake continues while assignment waits. Start workers and show the correct team worklists being populated. For failure, accept a well-formed request whose category has no configured route; the worker cannot resolve it, retries, and reaches DLQ. Add the missing routing rule and redrive the job; the ticket becomes assigned. This cleanly demonstrates that changing database business configuration can repair failed processing.

### Natural Review 2 examples

| Criterion | Proposed visible proof |
|---|---|
| Tables/constraints/validation | Customer/ticket/team/rule relationships; invalid customer FK and forbidden priority are rejected |
| Insertion/management | Create request; worker assigns team; operator adds a route and requeues a failed job |
| Queries/filtering/aggregation/joins | Open high-priority tickets; customer/ticket/team JOIN; count unassigned requests per category; team workload GROUP BY with HAVING |
| Advanced features | Queue functions and claiming transaction; ticket-result uniqueness for repeat safety; existing audit/view/index features |
| Presentation | One request with traceable ID becomes a team work item; missing rule explains failure and repair clearly |

Do not claim Conduit presently prioritizes queue delivery because the support domain has a priority field. Priority can be a filter/report attribute unless delivery scheduling is explicitly implemented and tested.

## 3. Asynchronous business report/export generation

### Real-world grounding

Power BI's official ExportToFile API starts an asynchronous report export job and provides an API to track its status. This establishes report export as a real asynchronous business operation. The proposed Conduit demo would generate its own local CSV, not integrate with Power BI or inherit its capabilities. [Microsoft Power BI ExportToFile](https://learn.microsoft.com/en-us/rest/api/power-bi/reports/export-to-file).

Microsoft's background-job guidance separately identifies data analysis for daily reports as a scheduled background task. Our small demonstration can use an explicit “Generate report” request; a scheduler is optional and should not be implied to exist. [Microsoft background-job guidance](https://learn.microsoft.com/en-us/azure/architecture/best-practices/background-jobs).

### Small proposed demo

A fictional service business wants monthly invoices/outstanding-balance reports. The user selects a date range and clicks Generate. A `report-jobs` message carries request ID, report type, and parameters. A separate worker executes a named SQL query and writes a real downloadable CSV plus a result row. Show the exact query and verify a few CSV totals against the database output.

Proposed supporting entities: `customer`, `invoice`, `invoice_line`, `report_request`, and `report_result`, reduced if some are unnecessary. Constraints: invoice/customer FK, line/invoice FK, positive quantity, nonnegative amount, valid report date range, allowed report type, and unique result/request identity. A local service-business invoice report is distinct from building an e-commerce checkout.

### Faculty-visible success and failure

Submit two reports while workers are stopped, then start workers and download the resulting files. Show date filtering, JOINs, SUM, GROUP BY, and HAVING before showing their CSV output. An invalid date range should be rejected at intake. For a processing failure, use a clearly labelled fixture that makes an otherwise valid request unable to write its output; retry and DLQ record the problem, and restoring the output destination lets redrive succeed.

### Natural Review 2 examples

| Criterion | Proposed visible proof |
|---|---|
| Tables/constraints/validation | Invoice/line/customer/request/result ER slice and date/quantity/FK rejection examples |
| Insertion/management | Seed invoices; enqueue requests; update job states; publish result metadata and downloadable CSV |
| Queries/filtering/aggregation/joins | Customer/invoice/line JOIN; invoice date WHERE; SUM quantities/amounts by customer; HAVING total > chosen threshold; ORDER BY total |
| Advanced features | A useful reporting view; existing broker functions/triggers/partial indexes; transactional enqueue; EXPLAIN on appropriately sized fixtures |
| Presentation | “Generate monthly outstanding balances” -> stored request -> worker SQL -> real CSV; verify the same figures in SQL |

This scenario is particularly good if the faculty expects recognizable relational business data. Generating a tiny CSV is fast, so explain that fixtures reproduce the workflow and reliability of larger exports rather than claiming that five rows justify a performance optimization.

## Shared evidence discipline

For any option, show an action, the stored data change, the relevant SQL feature, and the observed result. A feature list alone is weaker evidence than tracing one real job. Existing Conduit tables already provide identity/application relationships, message-topic/application JOINs, schema metadata, delivery states, producer deduplication, DLQ, and audit.

Source-verified existing features include `produce`, `consume`, acknowledgement/retry routines, `v_topic_stats`, `v_audit_recent`, `v_throughput_by_minute`, audit triggers, and pending/claim indexes. The PostgreSQL SELECT documentation explicitly identifies `SKIP LOCKED` as suitable for multiple consumers of queue-like tables, while warning it is not a general consistent query view. [PostgreSQL 16 SELECT](https://www.postgresql.org/docs/16/sql-select.html).

Show pending/claimed/delivered/dead counts from stored statuses during the live demo. Prior runtime probes found that committed-offset lag can become zero despite unfinished earlier jobs; do not use that metric as the sole proof of completed business work. Existing functions are SQL functions, not `CREATE PROCEDURE` procedures. The rubric lists examples “as applicable”; demonstrate the useful features actually present and do not manufacture features only to match every word.

Files in this research are notes only. The scenario choice should precede implementation of business tables, producer/worker code, queries, and presentation changes.
