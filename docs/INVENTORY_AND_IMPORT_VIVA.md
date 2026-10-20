# Inventory Management and Sales import: viva answers

20 October 2026. Presentation additions are prepared for Updated_Conduit_Final_Presentation.pptx. Slides32–36 cover threshold UPSERT, product dropdown, receipt SQL, sale validation/header/item SQL and sale balance/ledger SQL. Each includes recorded output. Application data is unchanged: all controlled product900005 receipt/sale/threshold tests were rolled back. Full function implementation is retained in speaker notes. All original slides/media and ER diagrams are preserved.

## Answer: why Sales import does not deduct stock

“Sales import is a historical data-onboarding workflow. It loads existing sales records from CSV so that we can validate them, analyse previous business and generate statements. Those sales occurred before being imported; their physical stock effect may already be included in the retailer's opening stock count. We therefore do not treat importing a record as a new stock dispatch. New physical sales go through Inventory, where one database transaction creates the sale and deducts stock.”

Example: the retailer starts using Conduit today and counts50keyboards. Last month it sold10keyboards, and that past sale is already reflected in today's physical count. Importing last month's sales should enrich sales history while leaving today's50units intact. Deducting10again would incorrectly show40units.

This is the current application's explicit scope: the CSV workflow always imports historical sales facts; it does not determine whether an arbitrary uploaded file was already reflected in stock. Do not claim the application automatically detects that business distinction. A new-unprocessed-sales import mode would require explicit inventory semantics, stock checks, reference/retry protection and atomic posting through the stock workflow. That integration is not currently implemented.

## Answer: what is the purpose of Sales import?

“A retailer may already have sales in spreadsheets or exports from an older system. Sales import brings those records into our normalized PostgreSQL database without requiring manual entry of every order line. It maps external headers, stages the original rows, validates them, quarantines complete invalid orders and commits complete valid orders. The accepted facts are then available to the same SQL queries, analysis and report-generation pipeline as other sales.”

### Explain the steps

1. **Upload:** read a UTF-8CSV of existing sales. The current limit is2MB/2000lines. Existing customers and products must already be known; import does not invent master records.
2. **Map:** map headings such asOrderNo/ClientCode/Qty/Rate to order_ref/customer_ref/quantity/unit_price. Local aliases and manual confirmation work without AI; optional Gemini suggests header mapping.
3. **Stage:** store raw input, mapping, cleaned values, validation errors and row states in import_batch/import_row. A preview row is not yet an authoritative sales order.
4. **Validate:** check required fields, dates, quantities/prices, references and order consistency. Database constraints separately enforce their declared rules on publication.
5. **Accept whole orders:** one invalid line quarantines its whole order rather than storing a partial version. Other independent valid orders can be committed.
6. **Detect duplicates/conflicts:** find an existing order_ref and compare customer,date,status and all line identities/SKUs/quantities/prices. Same reference+same content is skipped; same reference+different content is rejected. The commit path rechecks under a reference lock. A new reference is treated as a new business order; this is not fuzzy duplicate detection.
7. **Publish:** create sales_order/order_item records transactionally. Reference fields resolve to product/customer foreign keys. Staging states record which rows were imported, rejected or duplicates.
8. **Repair:** correct rejected data in a new CSV and retry. The original rejected evidence is retained; accepted identical orders are not duplicated. This does not silently edit an already accepted conflicting sale.
9. **Use the data:** approved JOIN/filter/aggregate/window queries, Analysis and downloadable reports include the accepted completed sales within the selected dates.

### Explain the value

The section addresses inconsistent exported data, repeated uploads and manual order-line entry. It demonstrates staging, normalization,INSERT/SELECT/UPDATE,PK/FK/UNIQUE/NOTNULL/CHECK,joins,transactional publication and inspectable rejection history. Validation improves structural/business-rule consistency; it cannot prove that every plausible uploaded value matches an actual external invoice.

### Example from the demo

- First file: GOODorder has2×25.00+1×50.00=100.00; BADorder contains-10.00.
- First commit: GOODis published; BADstays rejected in staging.
- Corrected file: GOODis identical and skipped; BADnow10.00is accepted.
- Accepted value across the pair:110.00,with no second copy ofGOOD.
- Queries and reports see these accepted facts. Inventory does not move because this is historical onboarding.

## Threshold explanation

Save threshold uses INSERT...ONCONFLICT(product_id)DOUPDATE: an UPSERT. Existing products retain their stock quantity when the threshold changes. A missing balance row starts at the database default0. v_inventory calculates quantity<=reorder_level as low_stock. This is an alert rule, not an automatic supplier purchase/replenishment feature.

## Presentation evidence

- Threshold fixture:10units,threshold12,low_stock=true; command tagINSERT01.
- Dropdown query returned33products; the slide explicitly shows its first3rows as an excerpt.
- Receipt fixture:0→10,ledger10,movement13.
- Sale fixture:3units at75.00,total225.00;10→7,ledger7,reconciled=true,movement14.
- SQL branches on the slides are readable equivalents/excerpts from post_stock, labelled as function internals. The actual full CASE-based function is in the notes. Its checks/reference locks and complete body are not being replaced by the shortened snippets.

Private build/validation/source backups: `.local/ppt_inventory_20261020/`. The authoritative presentation is saved and its hash matches the validated revision. The user confirmed no new changes before closing PowerPoint. All five added slides were visually reviewed; package, font and first-party import checks passed with no layout findings or warnings. All87 retained slides/media were preserved except footer numbering. The five new Inventory Management slides are32–36.
