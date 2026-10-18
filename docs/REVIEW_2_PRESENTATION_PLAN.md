# Review 2 presentation audit and revision plan

Current authoring reference: [PPT_REFERENCE.md](PPT_REFERENCE.md), created after the reporting implementation and evaluator discussion. It records the user's mandatory normalization examples and the verified full-schema appendix. The audit below describes the older deck; use current implementation evidence for the replacement.

This reviews the existing 17-slide `Conduit_DBMS_Review_2.pptx` and accompanying presentation script. It does not replace or edit them. The user requested analysis now and a new deck later.

The deck contains considerable relevant material, but it reads like a compressed technical report. It foregrounds feature counts and broad guarantees instead of helping an evaluator follow the database design, execute an operation, and judge its result. Correctness and explanation need to precede visual polish.

## 1. Why the current deck is difficult to present

Text extraction found approximately 160–208 words on most technical slides. Many explicit body runs are 9–11 points. Representative renders show very small text at the top of large panels, leaving substantial unused space below. This makes projected text hard to read even when it does not physically overflow.

Slide 3 lists fifteen tables and attributes, but shows no ER relationships. Slide 8 includes actual SQL, but mixes that evidence with inaccurate lock and concurrency claims. Slide 17 has a dense evidence matrix and announces an unsupported perfect score. Its matrix omits the fifth grading criterion, presentation.

The deck often assumes the audience already understands producer sequences, group offsets, physical partitions, RLS, and WAL. Establish these through one message example before relying on them. Show short code with a result, then explain what it proves.

## 2. Slide-by-slide review

| Existing slide | Assessment | Revision action |
|---|---|---|
| 1. Title and team | Relevant introduction, but the “high-throughput” framing is stronger than the retained evidence warrants | Use “Conduit: A PostgreSQL-backed message queue” or equivalent; keep team and Review 2 identity concise |
| 2. Review 1 evolution | Important design change, but unnecessarily criticizes the completed review and calls SKIP LOCKED lock-free | Explain the revised design neutrally; explicitly show what storage responsibility moved into PostgreSQL |
| 3. Relational schema | Fifteen-table inventory is hard to absorb; 3NF/BCNF assertion lacks a dependency analysis | Show the implemented ER core with keys and cardinalities; explain role normalization and the two junction tables |
| 4. Constraints and validation | Contains useful DBMS evidence but overclaims universal validation and quotes a historical catalog count | Show one FK rejection, one CHECK rejection, and required-field validation with actual output; use the real `validate_schema` name |
| 5. Physical partitioning | Mixes logical and physical partitioning, historical FK discussion, and unsupported zero-downtime claims | Diagram the two kinds of partition; show `PARTITION BY RANGE` and one catalog boundary; state retention/drop limitations |
| 6. Produce pipeline | A useful operation, but unkeyed routing is not strict round-robin and the timestamp-sequence bug is absent | Explain one message's path through partition counter, message, ledger, and audit within a transaction |
| 7. Seed and housekeeping | Demonstrates data management, but seed timestamps use randomness and maintenance has no scheduler | Show counts measured from the demo database and one retry/DLQ example; call maintenance explicitly invoked functions |
| 8. Consume query | The strongest SQL-centered slide, weakened by small code and incorrect concurrency wording | Use a larger query excerpt; explain row locks and skipping separately; current Python race uses 30 messages and three threads, not the slide's 12-message process example |
| 9. Joins and aggregates | Directly relevant to grading, but the lag SQL is not the implemented view definition | Show one actual join and one FILTER aggregate with readable result rows; describe current offset-gap limitation |
| 10. Functions and transactions | Atomic acknowledgement is real, exactly-once processing claim is not | Name SQL/PLpgSQL functions accurately; show atomic status/offset update or rollback; correct SQLSTATE list from source |
| 11. Triggers | Good advanced feature material, but count, names, immutability, and automatic failure logging are inaccurate | State 14 declared triggers; show one trigger definition and its observable effect; distinguish explicit failure logging |
| 12. RLS | Useful permitted-versus-unpermitted comparison, but quoted helper names do not exist | Show the actual policy and identity flow; fix protected web reads before claiming end-to-end isolation |
| 13. Indexes and EXPLAIN | Good retained plan evidence with inaccurate complexity and BRIN-saving claims | Highlight actual pending index and plan nodes; use retained 1.665 ms, dataset size, and environment caveat; omit O(1)/99% assertions |
| 14. Materialized views and recovery | Combines unrelated features and inflates the crash demo | Separate or move to appendix; WAL demo checks five acknowledged messages; dashboard currently reads normal views |
| 15. Benchmarks | Relevant optional evaluation, but speedups and consume attribution are wrong | Use retained JSON: ~495/1521/2562 produce, ~1856 batch consume, ~268 five-worker drain; emphasize workload conditions and batching |
| 16. Dashboard and demos | Demonstration assets are useful, but this remains a list of features | Replace with a short live-demo sequence and actual result screenshot/output; state what has been freshly verified |
| 17. Rubric coverage | Helpful concept, incorrect “10/10” conclusion and incomplete criterion list | Map all five criteria to specific evidence, without awarding a score to yourselves |

The same corrections must reach `REVIEW_2_PRESENTATION_SCRIPT.md`, which currently repeats several overclaims. Otherwise the spoken defense will contradict the corrected slides.

## 3. Proposed structure for the later replacement deck

This is a suggested sequence, not a mandated slide count or review time limit. Confirm any evaluator-specific format before authoring.

| Slide | Subject | Visible evidence | Presenter explanation |
|---|---|---|---|
| 1 | Conduit and the problem | Team, project title, one service-to-worker example | A durable queue decouples request handling from later work |
| 2 | Current scope and architecture | Browser/API/SDK/PostgreSQL diagram | PostgreSQL now stores and serves messages; current scope is a shared work queue |
| 3 | Current relational model | ER core with PK/FK and cardinalities | Why application, subscription, ledger, and per-partition offset tables exist |
| 4 | Constraints and payload validation | Short DDL excerpt and rejected input result | Distinguish declarative integrity from required-field validation |
| 5 | Example data | Current counts and a few anonymized sample rows | Explain users, apps, topics, and message states using the dataset |
| 6 | Message production | Function call, message row, ledger row | Atomic insertion, allocation, and retry deduplication |
| 7 | Claiming and settlement | State diagram and consume/ack results | Row locks, SKIP LOCKED, visibility timeout, and retries |
| 8 | SQL operations | Filtered query and actual join/aggregate result | Satisfy the queries/filtering/joins/aggregation criterion explicitly |
| 9 | Functions, triggers, and transactions | One trigger effect and a rollback example | Database-side behavior and why consistency is preserved |
| 10 | Access control and indexing | RLS result comparison, index definition, plan excerpt | State the trust boundary and explain the observed index use |
| 11 | Demonstration and validation | Produce-to-ack sequence and fresh test summary | Explain what ran successfully and which edge cases were checked |
| 12 | Rubric coverage and limitations | Five-row assessment matrix | Evidence for each criterion, honest current limitations, questions |

Possible appendix: full schema, window query, materialized view, WAL survival test, measured benchmarks, detailed SQLSTATE map, or retained execution plans. Use these for questions rather than forcing every feature into the main talk.

## 4. Content rules for the replacement deck

- Prefer one readable SQL excerpt plus its output over a paragraph describing SQL features.
- Make body text substantially larger than the current 9–11 points; around 20–24 points is a reasonable starting point for projected technical slides, adjusted to the actual venue and requested template.
- Put full SQL, secondary numbers, and detailed explanations in notes or appendix.
- Keep names identical to the implemented database objects. Do not invent helpers or copy planned SQL as implemented SQL.
- Use an actual current ER diagram and distinguish logical topic partitions from monthly child tables.
- Label retained historical benchmarks as historical. A new run needs source revision, environment, dataset, and test conditions.
- Use screenshots only from a working current build and keep SQL/results legible. Do not show invented success outputs.
- State the Review 1 architecture change clearly. Avoid claiming that a completed review failed.
- Cover presentation as the fifth criterion. Do not state a guaranteed mark or use “rubric saturation.”

## 5. Rehearsal questions

1. Where does a message physically live, and which primary key identifies it?
2. Why is `producer_sequence` separate from the partitioned message table?
3. What is the difference between a logical partition and a PostgreSQL child table?
4. Which rows does FOR UPDATE lock, and what does SKIP LOCKED skip?
5. What happens if a consumer completes work but crashes before ack?
6. What does the recorded offset mean when messages finish out of order?
7. Can two different groups both receive the same message in this implementation?
8. What does the payload validator enforce, and what does it leave unchecked?
9. Which SQL result demonstrates a join, and which demonstrates aggregation?
10. What exactly did the crash test prove?

Use [the project explanation](PROJECT_ANALYSIS.md) for answers grounded in the current code, and [the grading audit](REVIEW_2_READINESS.md) for corrections that must precede a confident demonstration.
