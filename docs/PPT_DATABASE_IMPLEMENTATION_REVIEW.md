# Database implementation evidence for the final presentation

Updated 20 October 2026. Continue editing only `Updated_Conduit_Final_Presentation.pptx`. Preserve the user's ER diagrams and leave the architecture/workflow proposal pending review.

Status: revised deck applied to the authoritative file and its hash verified against the validated revision, with 44 visible slides and 29 preserved hidden appendix slides. All 66 retained slides match the prior source except page numbering; original media are unchanged. Finalizer package and font checks passed, with no layout findings or warnings. New/changed slides were visually checked. After the user closed PowerPoint, its save renumbered package parts and added group transform metadata; logical slide text and media remained unchanged. Both source copies are backed up privately.

Revised section locations: slide 20 DBMS choice; 21 CREATE TABLE; 22 constraints; 23 order INSERT and output; 24 item INSERT and output; 25 transactional import; 26 JOIN/output; 27 HAVING/output; 28 window/output.

## Required coverage after normalization

1. DBMS choice: PostgreSQL 16.15, verified against the running local server. SQL is the language, PostgreSQL is the database management system. Explain relational integrity, transactions/locking, SQL and stored logic, JSONB alongside normalized tables, and local deployment without a licence fee.
2. CREATE TABLE: retain the existing executable equivalent of the current order_item definition. The original migration's generated line_total column was removed by a later migration; current sales views calculate the total.
3. Constraints: give PRIMARY KEY, FOREIGN KEY, UNIQUE, NOT NULL and CHECK examples from the actual schema, and explain each rule. NOT NULL rejects SQL NULL, not every empty string. Overselling is checked in post_stock with locking, rather than a cross-table CHECK.
4. INSERT and output: demonstrate an order header followed by three items referencing existing customer/product rows. Use INSERT ... RETURNING to display the stored rows and show INSERT 0 1 / INSERT 0 3 command tags.
5. SQL queries and outputs: show complete returned columns/rows for the existing four-table JOIN, category aggregation/HAVING and customer window-total examples. Shortened display headings may improve legibility without removing values.

## Captured evidence

All five SQL statements executed successfully against the local PostgreSQL server. The INSERT example used unused explicit order ID 900001, reference PPT-REVIEW-001, date 2026-10-20, existing customer 1 and products 3/4/5. Item quantities/prices are 3 at 75.00, 4 at 100.00 and 1 at 125.00; their sum is 750.00. The test used BEGIN/ROLLBACK. Its absence was checked after rollback. Explicit identity override avoided consuming sequence values. Application inserts normally allow PostgreSQL to generate IDs.

The read queries executed before these temporary inserts, in one repeatable-read transaction. The live window total was 25550.00, replacing the 18 October snapshot of 25500.00 in that slide. The window is evaluated over all matching rows before LIMIT 3. Its total is therefore distinct from the first displayed order's 750.00.

The full JOIN returned three item rows worth 225.00, 400.00 and 125.00. HAVING returned Office at 104988900.00. These are dated outputs of the synthetic demo database, not claims about real retailer revenue.

## How to present outputs

Place readable editable result tables beneath the SQL. Show real field values, the returned row count where useful, and capture date. INSERT RETURNING is stronger evidence than an 'insert successful' message because the evaluator can inspect the inserted data. Execute the query live in the application's query demonstration when appropriate; the saved slide remains the recorded reference.

## Sources

- Project migrations: 060_reporting_schema.sql, 110_normalized_sales_totals.sql, 150_retail_operations.sql.
- PostgreSQL constraints: https://www.postgresql.org/docs/16/ddl-constraints.html
- Transactions: https://www.postgresql.org/docs/16/tutorial-transactions.html
- Window functions: https://www.postgresql.org/docs/16/tutorial-window.html
- JSON types: https://www.postgresql.org/docs/16/datatype-json.html

Private build evidence and source backup are retained under `.local/ppt_db_implementation_20261020/` and are not intended as presentation deliverables.
