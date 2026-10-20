# Working presentation and required structure

User instruction recorded 20 October 2026.

## Authoritative file

Edit **Updated_Conduit_Final_Presentation.pptx** in the repository root for all future presentation changes. It contains the user's own edits. Do not regenerate it from the older deliverables presentation or discard the user's ER images, title styling or other customisations. Preserve a private backup before modifying it.

Discuss proposed changes in chat first. Apply changes when the user authorises them. This revision authorises the dedicated problem/abstract/objectives slides, main relational schema slides and the expanded normalization section.

## Required main-deck order

1. Title
2. Problem Statement
3. Abstract
4. Objectives and Scope (objectives on a dedicated bullet-point slide)
5. System Architecture / Workflow
6. ER Diagram
7. Relational Schema and Normalization
8. Database Implementation: DBMS used, CREATE TABLE, PK/FK/UNIQUE/NOT NULL, sample INSERT records, SQL queries and outputs
9. Advanced Database Concepts: procedures/functions, triggers, views, COMMIT/ROLLBACK
10. Application Screenshots / Demonstration
11. Testing and Results
12. Conclusion and Future Enhancement
13. References

Keep the detailed schema and additional SQL appendix as backup. Present only demo-related relations, not the total legacy/infrastructure table count.

## Preservation and pending changes

- **Do not add or replace ER diagrams.** The user has already supplied updated sales and inventory ER image slides.
- **Do not change architecture/workflow content yet.** A smaller architecture proposal must first be reviewed in chat. Page numbering and ordering may change as sections are inserted.
- Three main schema slides precede normalization: sales, inventory, and report execution. The full dictionary stays in the appendix.
- Replace the original two normalization slides with five steps: actual starting records, UNF to1NF, partial dependencies/2NF, transitive dependencies/3NF, and the final model with historical sale-price treatment.
- Use the actual existing demo order DEMO-000001-1:2026-01-09, customer1, products3/4/5, quantities3/4/1, prices75/100/125 and order value750.00. These are synthetic project fixtures, not real-world customer data.
- Explain a reconstructed decomposition honestly. Do not claim the deployed database historically passed through UNF,1NF and2NF versions.

## Validation explanation for viva

Application layer: reporting/imports.py, validate() and commit() check headers, dates, numbers, reference existence, same-order customer/date consistency, duplicate line numbers and matching/conflicting business content. This gives preview errors and whole-order quarantine.

Database layer: db/migrations/060_reporting_schema.sql and later migrations define PK/FK/UNIQUE/NOT NULL/CHECK restrictions. Stock posting rules and row locking are in reporting.post_stock in150_retail_operations.sql. PostgreSQL independently enforces constraints when rows are written.

The DBMS concepts are domain/entity/referential integrity and transaction consistency. Python preview validation supports the workflow but is not itself a database constraint.

## Compact architecture proposal, not applied

Browser communicates with FastAPI, which connects to PostgreSQL. The database holds business records, constraints, reporting SQL and committed jobs. Separate Python workers prepare saved datasets and generate CSV/HTML files. FastAPI supplies status and downloads. Keep optional Gemini as a short annotation rather than another large processing chain.

Suggested compact diagram: Browser <-> FastAPI <-> PostgreSQL <-> Worker -> CSV/HTML. This is a component overview; the application serves the generated files to the browser. Wait for the user's approval before replacing the existing architecture/workflow slides.
