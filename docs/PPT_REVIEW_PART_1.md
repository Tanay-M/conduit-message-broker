# Final presentation review, part 1

Reviewed 20 October 2026. Initial status was proposals for discussion. The user subsequently approved the expanded normalization section and new problem/abstract/objectives/main-schema slides in **Updated_Conduit_Final_Presentation.pptx**. The revised deck is applied in that authoritative file and matches the validated revision. The user closed PowerPoint to release its file lock; the intervening save changed only metadata and an internal text flag, with no content or layout changes. Both source copies are backed up privately. Architecture/workflow simplification remains pending chat review. The user's own ER image slides are preserved. Future deck edits still require chat review followed by authorisation.

## User questions

1. Explain slide 2's dependable-data statement with a scenario.
2. Supply a more detailed, simple system architecture diagram in chat.
3. Replace slide 7's block diagram with an ER model showing named attributes, relationship diamonds and cardinalities, following the supplied sample's style.
4. Expand slides 9/10 into a step-by-step normalization explanation using actual project records, with extra slides if needed.
5. Explain slide 13, transactional import and correction.

Numbering: the inspected export has Objectives on slide 3 and Architecture on slide 4. Use titles to avoid confusion if the user's edited copy has shifted numbers.

## Dependable-data scenario

The provided import file contains a good order with two lines: 2 units at 25.00 plus 1 unit at 50.00, total 100.00. A different order has a line priced at -10.00. Summing both indiscriminately gives 90.00. Reimporting the good order without duplicate protection would count it twice. These arithmetic/duplication problems show why an accurately executed SUM alone is insufficient.

Conduit stages inputs, rejects invalid orders, checks customer/product references and detects identical business content. The first commit accepts 100.00 and preserves the invalid order with an explanation. A corrected new import changes the rejected price to 10.00. It skips the identical good order and accepts the repaired order. The accepted value across these two example orders is then 110.00. These figures concern the example orders, not the entire existing database.

Proposed clearer slide wording: “Invalid or duplicate sales records produce misleading reports. Conduit validates orders before adding them to the reporting database.” This supports syntactic/relational correctness, not a guarantee that an externally supplied positive price is true.

## Architecture facts

- Browser uses a server-rendered workspace. FastAPI renders Jinja templates and serves local assets.
- FastAPI owns login/session checks and routes import, inventory, analysis, approved questions and report requests.
- PostgreSQL contains normalized business facts, staging and retained evidence, reporting state and internal queue records.
- Import, bounded interactive analysis and approved query execution run during a request. Report preparation/rendering uses background workers.
- Report submission calls submit_run. The transaction records the run and preparation job together.
- A worker executes SQL preparation in REPEATABLE READ and commits saved report datasets. It then enqueues bounded rendering work.
- Workers render CSV/HTML from retained data into local files, then record metadata/status and acknowledge the queue job in a database transaction.
- PostgreSQL transactions do not include filesystem writes. Output publication uses temporary files/rename, and retries check existing result metadata.
- A worker process can handle both job types. Preparation and rendering are phases, not necessarily dedicated separate services.
- Optional Gemini assists header mapping, supported question interpretation and aggregate explanations. PostgreSQL still performs the actual calculations and validation. No call per report is required.
- Local database and application do not require Redis, Docker, Kafka, a separate custom WAL engine or a distributed cluster.

## ER design proposal

Use the sample's hybrid notation: entities with actual column lists, PK/FK/UQ annotations, diamonds containing relationship verbs, and explicit endpoint cardinalities. This is a logical relational ER model with relationship diamonds. Do not call it strict Chen notation, which normally draws attributes as ovals.

Split the visual for readability:

1. Sales core: customer, sales_order, order_item and product.
2. Inventory extension: product, inventory_balance, stock_movement, and customer/sales_order references.
3. Reporting/history and import relations if extending the complete demo schema view. Keep assistant_request and analysis_run standalone where no declared FK exists. Do not invent links from actor text to a user table or from staged import rows to accepted orders.

Sales cardinalities:

- Each sales_order has exactly one customer. A customer may have zero or many orders.
- Each order_item has exactly one parent order. The database permits zero or many lines per order header; the import workflow accepts complete orders.
- Each order_item has exactly one product. A product may appear in zero or many order items.

Inventory cardinalities:

- Each inventory_balance references exactly one product. A product may be untracked or have one balance.
- Each stock_movement references exactly one product. A product may have zero or many movements.
- A movement has zero or one customer: receipts have none, sales require one. A customer may have zero or many sale movements.
- A movement has zero or one linked sales_order: receipts have none, sales require one. A sales_order has zero or one linked stock movement because stock_movement.order_id is UNIQUE. Historical imported sales can have no movement.
- There is no direct declared FK between inventory_balance and stock_movement. Their reconciliation follows their shared product_id.

## Normalization evidence and proposed sequence

Read-only query on 20 October retrieved this existing order:

- order_id 1, order_ref DEMO-000001-1, ordered_at 2026-01-09, status completed.
- customer_id 1, customer_ref DEMO-000001, full_name Customer 1, email customer1@example.test, region South.
- Line 1: product_id 3, SKU-3, Product 3, Office, quantity 3, historical unit_price 75.00, line value 225.00.
- Line 2: product_id 4, SKU-4, Product 4, Home, quantity 4, historical unit_price 100.00, line value 400.00.
- Line 3: product_id 5, SKU-5, Product 5, Electronics, quantity 1, historical unit_price 125.00, line value 125.00.
- Order total 750.00.

These are actual project database records, themselves synthetic demo data. Named catalogue products Wireless Keyboard (2499.00), Wireless Mouse (799.00) and USB-C Hub (1499.00) exist, but the read-only check found no current sale lines for them. Do not invent orders for them and present those as existing data.

Proposed five slides:

1. Starting flat representation and anomalies, reconstructed from this actual order. State that it illustrates decomposition, rather than falsely claiming an UNF database was once deployed.
2. UNF to 1NF: separate a repeating item list into atomic rows, key (order_id,line_number). Repeated customer/order/product metadata still remains.
3. 1NF to 2NF: remove attributes depending on only order_id from the composite item key. Put order_ref/customer/date/status in the order header. Keep line-specific product/quantity/sale price in items.
4. 2NF to 3NF: customer descriptions depend on customer_id, and product descriptions on product_id. Move those into customer/product and retain FKs. Show actual resulting rows and functional dependencies.
5. Final schema, JOIN reconstruction and legitimate derived/historical values. unit_price belongs to a particular sale line, while catalogue_price is current product metadata. line_total is calculated in v_sales_lines. Retained report JSON and inventory projections do not support an indiscriminate “every object is 3NF” claim.

Actual final sales columns:

customer(customer_id PK, customer_ref UQ, full_name, email UQ, region)
product(product_id PK, sku UQ, product_name, category, catalogue_price)
sales_order(order_id PK, order_ref UQ, customer_id FK, ordered_at, status)
order_item(order_id PK/FK, line_number PK, product_id FK, quantity, unit_price)

Important normal-form distinction: repetition of FK values is normal. The problem is repeating independently maintained descriptions/dependencies. A JOIN recreating repeated names in a result does not denormalize the stored authoritative relations.

## Slide 13 explanation

The visible INSERT is one part of publication, not the entire import algorithm. order_id identifies an existing newly created order header. line_number is the line's position within that order. product_id references an existing catalogue product. quantity and unit_price store the accepted sale facts. PostgreSQL checks PK/FK/NOT NULL/CHECK constraints on insert.

The colon placeholders on the slide are explanatory notation. The implemented Python SQL uses psycopg %s placeholders and supplies a separate parameter tuple. They should not be described as literal executable standalone PostgreSQL syntax.

Actual commit sequence: lock the batch; read/revalidate staged raw rows; group by order_ref; lock each reference against concurrent duplicate publication; check whether identical/conflicting accepted content exists; use a nested transaction/savepoint for each order; create its header and all lines; roll back an order on failure; record imported/duplicate/rejected row state; commit publication plus bookkeeping in the outer transaction.

One bad order does not discard other valid orders in the batch. A failure inside one order cannot leave only some of that order's lines committed. An unhandled outer failure rolls back the outer transaction. The original failed staged row is retained; a corrected upload is a new batch. Correction does not silently update already accepted orders. Identical retries skip, conflicting accepted content rejects.

Sources inspected: deliverables/Conduit_Final_Presentation.pptx; db/migrations/060_reporting_schema.sql, 110_normalized_sales_totals.sql and 150_retail_operations.sql; reporting/imports.py; reporting/worker.py; server/app/main.py. Live query evidence is privately saved in .local/presentation_review/part1-evidence.json.
