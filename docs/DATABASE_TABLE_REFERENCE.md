# Complete current database table and column reference

Verified against the running local PostgreSQL database on 18 October 2026. This is a schema-only catalog: no credential values or account/session contents were exported.

## Counting rule

- **28 logical tables**: 15 broker + 4 sales + 6 reporting/history + 2 login/session + 1 migration-history table.
- **27 domain/application/support tables** if the infrastructure-only schema_migration table is excluded.
- public contains 16 logical tables; reporting contains 12.
- **8 child storage partitions** of public.message are additional relations, not eight extra business entities.
- PostgreSQL catalogs therefore contain **36 table/partition relations** for these schemas when the partitioned parent and its children are included.
- The 28 logical table definitions have **177 columns** in total; inherited partition columns are not counted again.
- **6 ordinary views and 2 materialized views** are separate objects, excluded from the 28-table count.

PK = primary key; FK = declared foreign key; UNIQUE = alternate uniqueness restriction. Composite keys identify combinations, not each participating column independently.

## Overview

| Group | Table count |
|---|---:|
| Sales business facts | 4 |
| Reporting and history | 6 |
| Reporting login | 2 |
| Retained broker foundation | 15 |
| Migration infrastructure | 1 |

## Sales business facts

### reporting.customer — 5 columns

Authoritative customer facts for the fictional retailer.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `customer_id` | `bigint` | PK | No | Generated internal customer identifier. |
| `customer_ref` | `text` | UNIQUE | No | Unique readable business reference, e.g. DEMO-000001. |
| `full_name` | `text` | — | No | Customer name; required and not blank. |
| `email` | `text` | UNIQUE | No | Unique customer email address. |
| `region` | `text` | — | No | Customer region used for business classification. |

**Declared table constraints:**

- `customer_full_name_check`: `CHECK ((length(TRIM(BOTH FROM full_name)) > 0))`
- `customer_pkey`: `PRIMARY KEY (customer_id)`
- `customer_customer_ref_key`: `UNIQUE (customer_ref)`
- `customer_email_key`: `UNIQUE (email)`

**Generated values/defaults:**

- `customer_id` is generated ALWAYS AS IDENTITY.

### reporting.product — 5 columns

Authoritative current product/catalogue facts.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `product_id` | `bigint` | PK | No | Generated internal product identifier. |
| `sku` | `text` | UNIQUE | No | Unique stock-keeping/business product code; no inventory quantity is implemented yet. |
| `product_name` | `text` | — | No | Product description/name. |
| `category` | `text` | — | No | Product category label. |
| `catalogue_price` | `numeric(12,2)` | — | No | Current nonnegative catalogue price; distinct from historical sale-time price. |

**Declared table constraints:**

- `product_catalogue_price_check`: `CHECK ((catalogue_price >= (0)::numeric))`
- `product_pkey`: `PRIMARY KEY (product_id)`
- `product_sku_key`: `UNIQUE (sku)`

**Generated values/defaults:**

- `product_id` is generated ALWAYS AS IDENTITY.

### reporting.sales_order — 5 columns

Order header: customer, order identity, date and state.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `order_id` | `bigint` | PK | No | Generated internal order identifier. |
| `order_ref` | `text` | UNIQUE | No | Unique readable order reference. |
| `customer_id` | `bigint` | FK → reporting.customer(customer_id) | No | Customer who owns the order. |
| `ordered_at` | `date` | — | No | Order's business date, stored as DATE. |
| `status` | `text` | — | No | Order state: completed or cancelled; reporting excludes cancelled orders. |

**Declared table constraints:**

- `sales_order_status_check`: `CHECK ((status = ANY (ARRAY['completed'::text, 'cancelled'::text])))`
- `sales_order_customer_id_fkey`: `FOREIGN KEY (customer_id) REFERENCES reporting.customer(customer_id) ON DELETE RESTRICT`
- `sales_order_pkey`: `PRIMARY KEY (order_id)`
- `sales_order_order_ref_key`: `UNIQUE (order_ref)`

**Generated values/defaults:**

- `order_id` is generated ALWAYS AS IDENTITY.
- `status` defaults to `'completed'::text`.

### reporting.order_item — 5 columns

Individual order-line facts. No stored line_total in the final schema.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `order_id` | `bigint` | FK → reporting.sales_order(order_id); PK (composite) | No | Parent order; paired with line_number as the PK. |
| `line_number` | `integer` | PK (composite) | No | Positive line position within that order; part of the composite PK. |
| `product_id` | `bigint` | FK → reporting.product(product_id) | No | Product sold on this line. |
| `quantity` | `integer` | — | No | Positive integer units sold, bounded by the CHECK constraint. |
| `unit_price` | `numeric(12,2)` | — | No | Nonnegative historical price charged per unit on this sale line. |

**Declared table constraints:**

- `order_item_line_number_check`: `CHECK ((line_number > 0))`
- `order_item_quantity_check`: `CHECK (((quantity >= 1) AND (quantity <= 1000000)))`
- `order_item_unit_price_check`: `CHECK ((unit_price >= (0)::numeric))`
- `order_item_order_id_fkey`: `FOREIGN KEY (order_id) REFERENCES reporting.sales_order(order_id) ON DELETE RESTRICT`
- `order_item_product_id_fkey`: `FOREIGN KEY (product_id) REFERENCES reporting.product(product_id) ON DELETE RESTRICT`
- `order_item_pkey`: `PRIMARY KEY (order_id, line_number)`

## Reporting and history

### reporting.template_version — 6 columns

Approved immutable versioned business-report queries.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `template_id` | `bigint` | PK | No | Generated identifier of one specific template version. |
| `code` | `text` | UNIQUE (composite) | No | Report kind: customer_statement, product_sales or monthly_sales. |
| `version` | `integer` | UNIQUE (composite) | No | Positive version number within a report kind. |
| `title` | `text` | — | No | Readable report title. |
| `sql_text` | `text` | — | No | Approved parameterized SQL used for that template version. |
| `created_at` | `timestamp with time zone` | — | No | When the template version was recorded. |

**Declared table constraints:**

- `template_version_code_check`: `CHECK ((code = ANY (ARRAY['customer_statement'::text, 'product_sales'::text, 'monthly_sales'::text])))`
- `template_version_version_check`: `CHECK ((version > 0))`
- `template_version_pkey`: `PRIMARY KEY (template_id)`
- `template_version_code_version_key`: `UNIQUE (code, version)`

**Generated values/defaults:**

- `template_id` is generated ALWAYS AS IDENTITY.
- `created_at` defaults to `now()`.

### reporting.report_run — 13 columns

One submitted reporting operation, which can contain one or many individual reports.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `run_id` | `uuid` | PK | No | UUID identifying the submitted run/batch. |
| `submission_key` | `uuid` | UNIQUE | No | Unique client submission identity used for repeat-safe submission. |
| `template_id` | `bigint` | FK → reporting.template_version(template_id) | No | Exact immutable template version selected for the run. |
| `requested_by` | `bigint` | FK → app_user(user_id) | No | Configured broker administrator/requester identity in app_user; not yet per-browser-user attribution. |
| `customer_id` | `bigint` | FK → reporting.customer(customer_id) | Yes | Selected customer for a single statement; NULL for batch/summary scope. |
| `start_date` | `date` | — | No | Inclusive beginning of the reporting period. |
| `end_date` | `date` | — | No | Exclusive end of the reporting period. |
| `top_n` | `integer` | — | No | Requested product-ranking row limit, constrained to 1..100. |
| `bulk` | `boolean` | — | No | Whether to create a separate customer statement for every customer. |
| `status` | `text` | — | No | Dataset-preparation state: preparing, ready or failed; ready does not mean every file is complete. |
| `created_at` | `timestamp with time zone` | — | No | When the submission was recorded. |
| `prepared_at` | `timestamp with time zone` | — | Yes | When dataset preparation was marked ready. |
| `error` | `text` | — | Yes | Recorded preparation error, if any. |

**Declared table constraints:**

- `report_run_check`: `CHECK ((start_date < end_date))`
- `report_run_check1`: `CHECK (((end_date - start_date) <= 3660))`
- `report_run_status_check`: `CHECK ((status = ANY (ARRAY['preparing'::text, 'ready'::text, 'failed'::text])))`
- `report_run_top_n_check`: `CHECK (((top_n >= 1) AND (top_n <= 100)))`
- `report_run_customer_id_fkey`: `FOREIGN KEY (customer_id) REFERENCES reporting.customer(customer_id) ON DELETE RESTRICT`
- `report_run_requested_by_fkey`: `FOREIGN KEY (requested_by) REFERENCES app_user(user_id) ON DELETE RESTRICT`
- `report_run_template_id_fkey`: `FOREIGN KEY (template_id) REFERENCES reporting.template_version(template_id) ON DELETE RESTRICT`
- `report_run_pkey`: `PRIMARY KEY (run_id)`
- `report_run_submission_key_key`: `UNIQUE (submission_key)`

**Generated values/defaults:**

- `run_id` defaults to `gen_random_uuid()`.
- `top_n` defaults to `10`.
- `bulk` defaults to `false`.
- `status` defaults to `'preparing'::text`.
- `created_at` defaults to `now()`.

### reporting.report_request — 10 columns

One individual report subject/job within a run; not an HTTP request.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `request_id` | `uuid` | PK | No | UUID identifying one individual report. |
| `run_id` | `uuid` | FK → reporting.report_run(run_id); UNIQUE (composite) | No | Parent reporting run/batch. |
| `subject_key` | `text` | UNIQUE (composite) | No | Subject identity within the run, e.g. customer:1 or summary. |
| `customer_id` | `bigint` | FK → reporting.customer(customer_id) | Yes | Customer associated with this statement; NULL for a business summary. |
| `state` | `text` | — | No | Individual report state: queued, processing, completed or failed. |
| `created_at` | `timestamp with time zone` | — | No | When this individual request was created. |
| `completed_at` | `timestamp with time zone` | — | Yes | When this report was marked completed, if applicable. |
| `last_error` | `text` | — | Yes | Most recently recorded processing error, if any. |
| `attempts` | `integer` | — | No | Recorded rendering-attempt count for the individual report. |
| `enqueued` | `boolean` | — | No | Whether rendering work has been published to the internal queue. |

**Declared table constraints:**

- `report_request_attempts_check`: `CHECK ((attempts >= 0))`
- `report_request_state_check`: `CHECK ((state = ANY (ARRAY['queued'::text, 'processing'::text, 'completed'::text, 'failed'::text])))`
- `report_request_customer_id_fkey`: `FOREIGN KEY (customer_id) REFERENCES reporting.customer(customer_id) ON DELETE RESTRICT`
- `report_request_run_id_fkey`: `FOREIGN KEY (run_id) REFERENCES reporting.report_run(run_id) ON DELETE RESTRICT`
- `report_request_pkey`: `PRIMARY KEY (request_id)`
- `report_request_run_id_subject_key_key`: `UNIQUE (run_id, subject_key)`

**Generated values/defaults:**

- `request_id` defaults to `gen_random_uuid()`.
- `state` defaults to `'queued'::text`.
- `created_at` defaults to `now()`.
- `attempts` defaults to `0`.
- `enqueued` defaults to `false`.

### reporting.report_dataset — 3 columns

Immutable retained calculated content for historical replay.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `request_id` | `uuid` | FK → reporting.report_request(request_id); PK | No | Individual report identity; both PK and FK, allowing at most one dataset per request. |
| `rows` | `jsonb` | — | No | JSONB array of calculated report rows, including detail/aggregate values used for rendering. |
| `captured_at` | `timestamp with time zone` | — | No | When the retained dataset was recorded during preparation. |

**Declared table constraints:**

- `report_dataset_rows_check`: `CHECK ((jsonb_typeof(rows) = 'array'::text))`
- `report_dataset_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES reporting.report_request(request_id) ON DELETE RESTRICT`
- `report_dataset_pkey`: `PRIMARY KEY (request_id)`

**Generated values/defaults:**

- `captured_at` defaults to `now()`.

### reporting.report_result — 10 columns

At most one successful output-metadata row per individual report.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `request_id` | `uuid` | FK → reporting.report_request(request_id); PK | No | Individual report identity; both PK and FK, enforcing one successful result row per request. |
| `csv_path` | `text` | UNIQUE | No | Unique relative path to the generated CSV file. |
| `html_path` | `text` | UNIQUE | No | Unique relative path to the generated HTML file. |
| `csv_sha256` | `text` | — | No | Recorded SHA-256 checksum of CSV bytes. |
| `html_sha256` | `text` | — | No | Recorded SHA-256 checksum of HTML bytes. |
| `row_count` | `integer` | — | No | Number of saved report rows used in this output. |
| `worker_name` | `text` | — | No | Label of the worker publishing the result. |
| `sql_seconds` | `double precision` | — | No | Worker-measured database read/state/replay step duration; not the whole bulk-preparation or pure SQL-engine time. |
| `render_seconds` | `double precision` | — | No | Worker-measured rendering/file-publication duration in seconds. |
| `completed_at` | `timestamp with time zone` | — | No | When successful result metadata was recorded. |

**Declared table constraints:**

- `report_result_csv_sha256_check`: `CHECK ((csv_sha256 ~ '^[0-9a-f]{64}$'::text))`
- `report_result_html_sha256_check`: `CHECK ((html_sha256 ~ '^[0-9a-f]{64}$'::text))`
- `report_result_render_seconds_check`: `CHECK ((render_seconds >= (0)::double precision))`
- `report_result_row_count_check`: `CHECK ((row_count >= 0))`
- `report_result_sql_seconds_check`: `CHECK ((sql_seconds >= (0)::double precision))`
- `report_result_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES reporting.report_request(request_id) ON DELETE RESTRICT`
- `report_result_pkey`: `PRIMARY KEY (request_id)`
- `report_result_csv_path_key`: `UNIQUE (csv_path)`
- `report_result_html_path_key`: `UNIQUE (html_path)`

**Generated values/defaults:**

- `completed_at` defaults to `now()`.

### reporting.report_audit — 5 columns

Trigger-written report-state history, not a complete sales-edit audit.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `audit_id` | `bigint` | PK | No | Generated audit-event identifier. |
| `request_id` | `uuid` | FK → reporting.report_request(request_id) | No | Individual report whose processing state changed. |
| `old_state` | `text` | — | Yes | Previous processing state; NULL for a newly inserted request. |
| `new_state` | `text` | — | No | New processing state recorded by the trigger. |
| `event_at` | `timestamp with time zone` | — | No | When the state-change event was recorded. |

**Declared table constraints:**

- `report_audit_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES reporting.report_request(request_id) ON DELETE RESTRICT`
- `report_audit_pkey`: `PRIMARY KEY (audit_id)`

**Generated values/defaults:**

- `audit_id` is generated ALWAYS AS IDENTITY.
- `event_at` defaults to `now()`.

## Reporting login

### reporting.web_account — 5 columns

Reporting UI login accounts; separate from broker app_user identities.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `account_id` | `bigint` | PK | No | Generated browser-login account identifier. |
| `username` | `text` | UNIQUE | No | Unique username used on the simplified login screen. |
| `password_hash` | `text` | — | No | Salted PBKDF2-SHA256 password hash, not the plaintext password. |
| `enabled` | `boolean` | — | No | Whether login and existing sessions are allowed for this account. |
| `created_at` | `timestamp with time zone` | — | No | When the login account was created. |

**Declared table constraints:**

- `web_account_username_check`: `CHECK (((length(TRIM(BOTH FROM username)) >= 1) AND (length(TRIM(BOTH FROM username)) <= 64)))`
- `web_account_pkey`: `PRIMARY KEY (account_id)`
- `web_account_username_key`: `UNIQUE (username)`

**Generated values/defaults:**

- `account_id` is generated ALWAYS AS IDENTITY.
- `enabled` defaults to `true`.
- `created_at` defaults to `now()`.

### reporting.web_session — 4 columns

Expiring, revocable browser sessions for reporting administrators.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `token_hash` | `character(64)` | PK | No | SHA-256 hash of a random session token; primary lookup key, not an application API key. |
| `account_id` | `bigint` | FK → reporting.web_account(account_id) | No | Login account to which the session belongs. |
| `created_at` | `timestamp with time zone` | — | No | When the session was issued. |
| `expires_at` | `timestamp with time zone` | — | No | When the session stops authenticating; normally eight hours after creation. |

**Declared table constraints:**

- `web_session_check`: `CHECK ((expires_at > created_at))`
- `web_session_account_id_fkey`: `FOREIGN KEY (account_id) REFERENCES reporting.web_account(account_id) ON DELETE CASCADE`
- `web_session_pkey`: `PRIMARY KEY (token_hash)`

**Generated values/defaults:**

- `created_at` defaults to `now()`.
- `expires_at` defaults to `(now() + '08:00:00'::interval)`.

## Retained broker foundation

### public.role — 3 columns

Named broker permission roles.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `role_id` | `integer` | PK | No | Unique role identifier. |
| `role_name` | `character varying(32)` | UNIQUE | No | Role name, such as admin, operator, producer, consumer or viewer. |
| `description` | `character varying(255)` | — | Yes | Human-readable explanation of the role. |

**Declared table constraints:**

- `role_pkey`: `PRIMARY KEY (role_id)`
- `role_role_name_key`: `UNIQUE (role_name)`

**Generated values/defaults:**

- `role_id` defaults to `nextval('role_role_id_seq'::regclass)`.

### public.app_user — 6 columns

Broker user identities; report_run.requested_by references this table.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `user_id` | `bigint` | PK | No | Unique broker user identifier. |
| `username` | `character varying(64)` | UNIQUE | No | Unique broker username. |
| `email` | `character varying(255)` | UNIQUE | No | Unique email associated with the broker user. |
| `role_id` | `integer` | FK → role(role_id) | No | Assigned role in public.role. |
| `status` | `character varying(16)` | — | No | Whether the user is active or suspended. |
| `created_at` | `timestamp with time zone` | — | No | When the broker user was registered. |

**Declared table constraints:**

- `app_user_status_check`: `CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'suspended'::character varying])::text[])))`
- `app_user_role_id_fkey`: `FOREIGN KEY (role_id) REFERENCES role(role_id) ON DELETE RESTRICT`
- `app_user_pkey`: `PRIMARY KEY (user_id)`
- `app_user_email_key`: `UNIQUE (email)`
- `app_user_username_key`: `UNIQUE (username)`

**Generated values/defaults:**

- `user_id` defaults to `nextval('app_user_user_id_seq'::regclass)`.
- `status` defaults to `'active'::character varying`.
- `created_at` defaults to `now()`.

### public.application — 7 columns

Registered producer/consumer application identities retained from Review 1.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `app_id` | `bigint` | PK | No | Unique application identifier. |
| `app_name` | `character varying(128)` | UNIQUE | No | Unique application name, e.g. reporting-service. |
| `api_key` | `uuid` | UNIQUE | No | UUID application credential; retained internally, absent from the demo login UI. |
| `owner_user_id` | `bigint` | FK → app_user(user_id) | No | Broker user who owns this application. |
| `app_type` | `character varying(16)` | — | No | Whether the application can act as producer, consumer or both. |
| `status` | `character varying(16)` | — | No | Whether the application is active or revoked. |
| `created_at` | `timestamp with time zone` | — | No | When the application was registered. |

**Declared table constraints:**

- `application_app_type_check`: `CHECK (((app_type)::text = ANY ((ARRAY['producer'::character varying, 'consumer'::character varying, 'both'::character varying])::text[])))`
- `application_status_check`: `CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'revoked'::character varying])::text[])))`
- `application_owner_user_id_fkey`: `FOREIGN KEY (owner_user_id) REFERENCES app_user(user_id) ON DELETE CASCADE`
- `application_pkey`: `PRIMARY KEY (app_id)`
- `application_api_key_key`: `UNIQUE (api_key)`
- `application_app_name_key`: `UNIQUE (app_name)`

**Generated values/defaults:**

- `app_id` defaults to `nextval('application_app_id_seq'::regclass)`.
- `api_key` defaults to `gen_random_uuid()`.
- `status` defaults to `'active'::character varying`.
- `created_at` defaults to `now()`.

### public.topic — 8 columns

Named channels used to organize queued messages.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `topic_id` | `bigint` | PK | No | Unique topic identifier. |
| `topic_name` | `character varying(128)` | UNIQUE | No | Unique topic name, e.g. report-prepare or report-render. |
| `description` | `character varying(512)` | — | Yes | Purpose of the topic. |
| `created_by` | `bigint` | FK → app_user(user_id) | No | Broker user who created the topic. |
| `retention_days` | `integer` | — | No | Configured retention period for that topic's messages. |
| `max_message_bytes` | `integer` | — | No | Maximum accepted message-payload size for the topic. |
| `status` | `character varying(16)` | — | No | Whether the topic is active or archived. |
| `created_at` | `timestamp with time zone` | — | No | When the topic was created. |

**Declared table constraints:**

- `topic_max_message_bytes_check`: `CHECK ((max_message_bytes > 0))`
- `topic_retention_days_check`: `CHECK (((retention_days >= 1) AND (retention_days <= 3650)))`
- `topic_status_check`: `CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'archived'::character varying])::text[])))`
- `topic_created_by_fkey`: `FOREIGN KEY (created_by) REFERENCES app_user(user_id) ON DELETE RESTRICT`
- `topic_pkey`: `PRIMARY KEY (topic_id)`
- `topic_topic_name_key`: `UNIQUE (topic_name)`

**Generated values/defaults:**

- `topic_id` defaults to `nextval('topic_topic_id_seq'::regclass)`.
- `retention_days` defaults to `7`.
- `max_message_bytes` defaults to `1048576`.
- `status` defaults to `'active'::character varying`.
- `created_at` defaults to `now()`.

### public.partition — 4 columns

Logical queue-partition metadata; different from monthly PostgreSQL storage partitions.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `partition_id` | `bigint` | PK | No | Unique queue-partition identifier. |
| `topic_id` | `bigint` | FK → topic(topic_id); UNIQUE (composite) | No | Topic to which this queue partition belongs. |
| `partition_number` | `integer` | UNIQUE (composite) | No | Zero-based partition number within its topic. |
| `next_offset` | `bigint` | — | No | Next message offset to allocate in this queue partition. |

**Declared table constraints:**

- `partition_next_offset_check`: `CHECK ((next_offset >= 0))`
- `partition_partition_number_check`: `CHECK ((partition_number >= 0))`
- `partition_topic_id_fkey`: `FOREIGN KEY (topic_id) REFERENCES topic(topic_id) ON DELETE CASCADE`
- `partition_pkey`: `PRIMARY KEY (partition_id)`
- `uq_partition_topic_number`: `UNIQUE (topic_id, partition_number)`

**Generated values/defaults:**

- `partition_id` defaults to `nextval('partition_partition_id_seq'::regclass)`.
- `next_offset` defaults to `0`.

### public.schema_version — 8 columns

Versioned message payload contracts for a topic.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `schema_id` | `bigint` | PK | No | Unique message-contract identifier. |
| `topic_id` | `bigint` | FK → topic(topic_id); UNIQUE (composite) | No | Topic governed by this contract version. |
| `version` | `integer` | UNIQUE (composite) | No | Contract version number within that topic. |
| `format` | `character varying(16)` | — | No | Contract format; currently json. |
| `definition` | `jsonb` | — | No | JSONB message contract, including required-field definitions; not a claim of complete JSON Schema support. |
| `status` | `character varying(16)` | — | No | Whether this contract version is active or deprecated. |
| `created_by` | `bigint` | FK → app_user(user_id) | Yes | Broker user who published the contract, when recorded. |
| `created_at` | `timestamp with time zone` | — | No | When this contract version was published. |

**Declared table constraints:**

- `schema_version_format_check`: `CHECK (((format)::text = 'json'::text))`
- `schema_version_status_check`: `CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'deprecated'::character varying])::text[])))`
- `schema_version_version_check`: `CHECK ((version >= 1))`
- `schema_version_created_by_fkey`: `FOREIGN KEY (created_by) REFERENCES app_user(user_id) ON DELETE SET NULL`
- `schema_version_topic_id_fkey`: `FOREIGN KEY (topic_id) REFERENCES topic(topic_id) ON DELETE CASCADE`
- `schema_version_pkey`: `PRIMARY KEY (schema_id)`
- `uq_schema_topic_version`: `UNIQUE (topic_id, version)`

**Generated values/defaults:**

- `schema_id` defaults to `nextval('schema_version_schema_id_seq'::regclass)`.
- `format` defaults to `'json'::character varying`.
- `status` defaults to `'active'::character varying`.
- `created_at` defaults to `now()`.

### public.message — 13 columns

Persistent queue messages; the parent relation is range-partitioned by created_at.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `created_at` | `timestamp with time zone` | PK (composite) | No | Message creation time; also the PostgreSQL range-partition key and part of its composite PK. |
| `topic_id` | `bigint` | FK → topic(topic_id); PK (composite) | No | Topic containing this message. |
| `partition_id` | `bigint` | FK → partition(partition_id); PK (composite) | No | Logical queue partition containing this message. |
| `msg_offset` | `bigint` | PK (composite) | No | Sequence position within the logical queue partition; not a globally unique message ID. |
| `msg_key` | `character varying(128)` | — | Yes | Optional routing/correlation key; reporting uses a run/request UUID string. |
| `payload` | `jsonb` | — | No | JSONB job payload, such as a run_id or request_id. |
| `size_bytes` | `integer` | — | No | Recorded message-payload size in bytes. |
| `producer_app_id` | `bigint` | FK → application(app_id) | No | Application that produced the message. |
| `producer_seq` | `bigint` | — | No | Application-supplied sequence identity used for duplicate-publish detection. |
| `status` | `character varying(16)` | — | No | Delivery state: pending, claimed, delivered or dead. |
| `claimed_by` | `bigint` | FK → consumer_group(group_id) | Yes | Consumer group currently holding the claim; not an individual worker ID. |
| `visible_at` | `timestamp with time zone` | — | Yes | Claim-expiry/reavailability timestamp used by delivery and recovery logic. |
| `attempts` | `integer` | — | No | Number of message delivery claims attempted. |

**Declared table constraints:**

- `message_attempts_check`: `CHECK ((attempts >= 0))`
- `message_msg_offset_check`: `CHECK ((msg_offset >= 0))`
- `message_producer_seq_check`: `CHECK ((producer_seq >= 0))`
- `message_size_bytes_check`: `CHECK ((size_bytes >= 0))`
- `message_status_check`: `CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'claimed'::character varying, 'delivered'::character varying, 'dead'::character varying])::text[])))`
- `fk_message_claimed_by`: `FOREIGN KEY (claimed_by) REFERENCES consumer_group(group_id) ON DELETE SET NULL`
- `fk_message_partition`: `FOREIGN KEY (partition_id) REFERENCES partition(partition_id) ON DELETE RESTRICT`
- `fk_message_producer_app`: `FOREIGN KEY (producer_app_id) REFERENCES application(app_id) ON DELETE RESTRICT`
- `fk_message_topic`: `FOREIGN KEY (topic_id) REFERENCES topic(topic_id) ON DELETE RESTRICT`
- `message_pk`: `PRIMARY KEY (created_at, topic_id, partition_id, msg_offset)`

**Generated values/defaults:**

- `created_at` defaults to `now()`.
- `size_bytes` defaults to `0`.
- `status` defaults to `'pending'::character varying`.
- `attempts` defaults to `0`.

### public.producer_sequence — 6 columns

Producer idempotency ledger linking an application sequence to the original message coordinates.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `producer_app_id` | `bigint` | FK → application(app_id); PK (composite) | No | Producer application whose sequence is being recorded. |
| `producer_seq` | `bigint` | PK (composite) | No | Sequence value within that application; paired with producer_app_id as the PK. |
| `topic_id` | `bigint` | — | No | Recorded topic coordinate of the original message; no declared FK on this column. |
| `partition_id` | `bigint` | — | No | Recorded queue-partition coordinate; no declared FK on this column. |
| `msg_offset` | `bigint` | — | No | Recorded original message offset; no declared FK on this column. |
| `created_at` | `timestamp with time zone` | — | No | When this producer-sequence entry was recorded. |

**Declared table constraints:**

- `producer_sequence_msg_offset_check`: `CHECK ((msg_offset >= 0))`
- `producer_sequence_producer_seq_check`: `CHECK ((producer_seq >= 0))`
- `producer_sequence_producer_app_id_fkey`: `FOREIGN KEY (producer_app_id) REFERENCES application(app_id) ON DELETE CASCADE`
- `pk_producer_sequence`: `PRIMARY KEY (producer_app_id, producer_seq)`

**Generated values/defaults:**

- `created_at` defaults to `now()`.

### public.consumer_group — 6 columns

Consumer-group identities and delivery-attempt policy.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `group_id` | `bigint` | PK | No | Unique consumer-group identifier. |
| `group_name` | `character varying(128)` | UNIQUE | No | Unique name, e.g. report-preparers or report-workers. |
| `created_by` | `bigint` | FK → app_user(user_id) | Yes | Broker user who created the group, when recorded. |
| `max_delivery_attempts` | `integer` | — | No | Maximum delivery attempts before failure handling sends a message to the DLQ. |
| `status` | `character varying(16)` | — | No | Whether the group is active or paused. |
| `created_at` | `timestamp with time zone` | — | No | When the consumer group was created. |

**Declared table constraints:**

- `consumer_group_max_delivery_attempts_check`: `CHECK (((max_delivery_attempts >= 1) AND (max_delivery_attempts <= 10)))`
- `consumer_group_status_check`: `CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'paused'::character varying])::text[])))`
- `consumer_group_created_by_fkey`: `FOREIGN KEY (created_by) REFERENCES app_user(user_id) ON DELETE SET NULL`
- `consumer_group_pkey`: `PRIMARY KEY (group_id)`
- `consumer_group_group_name_key`: `UNIQUE (group_name)`

**Generated values/defaults:**

- `group_id` defaults to `nextval('consumer_group_group_id_seq'::regclass)`.
- `max_delivery_attempts` defaults to `3`.
- `status` defaults to `'active'::character varying`.
- `created_at` defaults to `now()`.

### public.group_subscription — 3 columns

Junction table representing consumer-group/topic subscriptions.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `group_id` | `bigint` | FK → consumer_group(group_id); PK (composite) | No | Subscribed consumer group; part of the composite PK. |
| `topic_id` | `bigint` | FK → topic(topic_id); PK (composite) | No | Topic to which the group subscribes; part of the composite PK. |
| `subscribed_at` | `timestamp with time zone` | — | No | When the subscription was created. |

**Declared table constraints:**

- `group_subscription_group_id_fkey`: `FOREIGN KEY (group_id) REFERENCES consumer_group(group_id) ON DELETE CASCADE`
- `group_subscription_topic_id_fkey`: `FOREIGN KEY (topic_id) REFERENCES topic(topic_id) ON DELETE CASCADE`
- `pk_group_subscription`: `PRIMARY KEY (group_id, topic_id)`

**Generated values/defaults:**

- `subscribed_at` defaults to `now()`.

### public.group_offset — 4 columns

Tracked settlement boundary per consumer group and logical queue partition.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `group_id` | `bigint` | FK → consumer_group(group_id); PK (composite) | No | Consumer group whose progress is tracked; part of the composite PK. |
| `partition_id` | `bigint` | FK → partition(partition_id); PK (composite) | No | Logical queue partition being tracked; part of the composite PK. |
| `committed_offset` | `bigint` | — | No | Contiguous settled-position boundary used for progress/lag; not a count of ack calls. |
| `updated_at` | `timestamp with time zone` | — | No | When the recorded progress boundary was last updated. |

**Declared table constraints:**

- `group_offset_committed_offset_check`: `CHECK ((committed_offset >= 0))`
- `group_offset_group_id_fkey`: `FOREIGN KEY (group_id) REFERENCES consumer_group(group_id) ON DELETE CASCADE`
- `group_offset_partition_id_fkey`: `FOREIGN KEY (partition_id) REFERENCES partition(partition_id) ON DELETE CASCADE`
- `pk_group_offset`: `PRIMARY KEY (group_id, partition_id)`

**Generated values/defaults:**

- `committed_offset` defaults to `0`.
- `updated_at` defaults to `now()`.

### public.access — 6 columns

User/topic permission grants.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `access_id` | `bigint` | PK | No | Unique grant identifier. |
| `user_id` | `bigint` | FK → app_user(user_id); UNIQUE (composite) | No | Broker user receiving permission. |
| `topic_id` | `bigint` | FK → topic(topic_id); UNIQUE (composite) | No | Topic to which permission applies. |
| `access_type` | `character varying(16)` | UNIQUE (composite) | No | Granted operation: produce, consume or admin. |
| `granted_by` | `bigint` | FK → app_user(user_id) | Yes | Broker user who issued the grant, when recorded. |
| `granted_at` | `timestamp with time zone` | — | No | When permission was granted. |

**Declared table constraints:**

- `access_access_type_check`: `CHECK (((access_type)::text = ANY ((ARRAY['produce'::character varying, 'consume'::character varying, 'admin'::character varying])::text[])))`
- `access_granted_by_fkey`: `FOREIGN KEY (granted_by) REFERENCES app_user(user_id) ON DELETE SET NULL`
- `access_topic_id_fkey`: `FOREIGN KEY (topic_id) REFERENCES topic(topic_id) ON DELETE CASCADE`
- `access_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app_user(user_id) ON DELETE CASCADE`
- `access_pkey`: `PRIMARY KEY (access_id)`
- `uq_access`: `UNIQUE (user_id, topic_id, access_type)`

**Generated values/defaults:**

- `access_id` defaults to `nextval('access_access_id_seq'::regclass)`.
- `granted_at` defaults to `now()`.

### public.dead_letter_message — 10 columns

Snapshot and error information for messages that exhausted delivery attempts.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `dlq_id` | `bigint` | PK | No | Unique dead-letter entry identifier. |
| `original_topic_id` | `bigint` | FK → topic(topic_id) | No | Original message's topic. |
| `original_offset` | `bigint` | — | No | Recorded original message offset; not a declared FK or globally unique source-message identity. |
| `msg_key` | `character varying(128)` | — | Yes | Copied correlation/routing key of the failed message. |
| `payload` | `jsonb` | — | No | Copied JSONB payload of the failed message. |
| `failed_group_id` | `bigint` | FK → consumer_group(group_id) | Yes | Consumer group associated with failure, when recorded. |
| `failure_reason` | `text` | — | Yes | Failure/error explanation. |
| `attempts` | `integer` | — | No | Recorded delivery-attempt count at failure. |
| `status` | `character varying(16)` | — | No | Whether the dead-letter entry is pending or has been requeued. |
| `dead_at` | `timestamp with time zone` | — | No | When the dead-letter entry was created. |

**Declared table constraints:**

- `dead_letter_message_attempts_check`: `CHECK ((attempts >= 0))`
- `dead_letter_message_original_offset_check`: `CHECK ((original_offset >= 0))`
- `dead_letter_message_status_check`: `CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'requeued'::character varying])::text[])))`
- `dead_letter_message_failed_group_id_fkey`: `FOREIGN KEY (failed_group_id) REFERENCES consumer_group(group_id) ON DELETE SET NULL`
- `dead_letter_message_original_topic_id_fkey`: `FOREIGN KEY (original_topic_id) REFERENCES topic(topic_id) ON DELETE RESTRICT`
- `dead_letter_message_pkey`: `PRIMARY KEY (dlq_id)`

**Generated values/defaults:**

- `dlq_id` defaults to `nextval('dead_letter_message_dlq_id_seq'::regclass)`.
- `attempts` defaults to `0`.
- `status` defaults to `'pending'::character varying`.
- `dead_at` defaults to `now()`.

### public.audit_log — 8 columns

Broker/admin event audit; separate from reporting.report_audit.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `log_id` | `bigint` | PK | No | Unique broker audit-event identifier. |
| `user_id` | `bigint` | FK → app_user(user_id) | Yes | Associated broker user, if recorded/still present. |
| `app_id` | `bigint` | FK → application(app_id) | Yes | Associated application, if recorded/still present. |
| `topic_id` | `bigint` | FK → topic(topic_id) | Yes | Associated topic, if recorded/still present. |
| `event_type` | `character varying(32)` | — | No | Event category, e.g. PRODUCE, DELIVERED or TOPIC_CREATE. |
| `status` | `character varying(16)` | — | No | Recorded event outcome: success or failure. |
| `details` | `jsonb` | — | Yes | JSONB event-specific details. |
| `event_timestamp` | `timestamp with time zone` | — | No | When the audit event was recorded. |

**Declared table constraints:**

- `audit_log_status_check`: `CHECK (((status)::text = ANY ((ARRAY['success'::character varying, 'failure'::character varying])::text[])))`
- `audit_log_app_id_fkey`: `FOREIGN KEY (app_id) REFERENCES application(app_id) ON DELETE SET NULL`
- `audit_log_topic_id_fkey`: `FOREIGN KEY (topic_id) REFERENCES topic(topic_id) ON DELETE SET NULL`
- `audit_log_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app_user(user_id) ON DELETE SET NULL`
- `audit_log_pkey`: `PRIMARY KEY (log_id)`

**Generated values/defaults:**

- `log_id` defaults to `nextval('audit_log_log_id_seq'::regclass)`.
- `status` defaults to `'success'::character varying`.
- `event_timestamp` defaults to `now()`.

### public.broker_config — 6 columns

Named broker configuration records with updater attribution.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `config_id` | `integer` | PK | No | Unique configuration-row identifier. |
| `config_key` | `character varying(64)` | UNIQUE | No | Unique setting name. |
| `config_value` | `text` | — | No | Text value stored for that setting. |
| `description` | `character varying(255)` | — | Yes | Human-readable description of the setting. |
| `updated_by` | `bigint` | FK → app_user(user_id) | Yes | Broker user associated with the latest recorded update. |
| `updated_at` | `timestamp with time zone` | — | No | When the configuration row was last updated. |

**Declared table constraints:**

- `broker_config_updated_by_fkey`: `FOREIGN KEY (updated_by) REFERENCES app_user(user_id) ON DELETE SET NULL`
- `broker_config_pkey`: `PRIMARY KEY (config_id)`
- `broker_config_config_key_key`: `UNIQUE (config_key)`

**Generated values/defaults:**

- `config_id` defaults to `nextval('broker_config_config_id_seq'::regclass)`.
- `updated_at` defaults to `now()`.

## Migration infrastructure

### public.schema_migration — 3 columns

Infrastructure bookkeeping for applied SQL scripts; not a business entity.

| Column | PostgreSQL type | Key/restriction | NULL allowed? | What it stores |
|---|---|---|---|---|
| `name` | `text` | PK | No | Relative migration/script path; identifies an applied script. |
| `sha256` | `text` | — | No | SHA-256 checksum of that applied script's content. |
| `applied_at` | `timestamp with time zone` | — | No | When the script was successfully applied. |

**Declared table constraints:**

- `schema_migration_pkey`: `PRIMARY KEY (name)`

**Generated values/defaults:**

- `applied_at` defaults to `now()`.

## Physical message storage partitions

These inherit the public.message column layout. They are storage children of one message entity. public.partition above is a different table describing logical queue partitions.

| Child relation | Range/default bound |
|---|---|
| `public.message_2026_09` | `FOR VALUES FROM ('2026-09-01 00:00:00+05:30') TO ('2026-10-01 00:00:00+05:30')` |
| `public.message_2026_10` | `FOR VALUES FROM ('2026-10-01 00:00:00+05:30') TO ('2026-11-01 00:00:00+05:30')` |
| `public.message_2026_11` | `FOR VALUES FROM ('2026-11-01 00:00:00+05:30') TO ('2026-12-01 00:00:00+05:30')` |
| `public.message_2026_12` | `FOR VALUES FROM ('2026-12-01 00:00:00+05:30') TO ('2027-01-01 00:00:00+05:30')` |
| `public.message_2027_01` | `FOR VALUES FROM ('2027-01-01 00:00:00+05:30') TO ('2027-02-01 00:00:00+05:30')` |
| `public.message_2027_02` | `FOR VALUES FROM ('2027-02-01 00:00:00+05:30') TO ('2027-03-01 00:00:00+05:30')` |
| `public.message_2027_03` | `FOR VALUES FROM ('2027-03-01 00:00:00+05:30') TO ('2027-04-01 00:00:00+05:30')` |
| `public.message_default` | `DEFAULT` |

## Views and materialized views (not tables in the count above)

| Name | Kind |
|---|---|
| `public.mv_topic_stats` | Materialized view |
| `public.v_audit_recent` | Ordinary view |
| `public.v_consumer_lag` | Ordinary view |
| `public.v_throughput_by_minute` | Ordinary view |
| `public.v_topic_stats` | Ordinary view |
| `reporting.mv_monthly_sales` | Materialized view |
| `reporting.v_run_progress` | Ordinary view |
| `reporting.v_sales_lines` | Ordinary view |

## Important interpretation notes

- A column ending in _id is not automatically an FK. The key labels and constraint definitions above come from PostgreSQL catalogs. In particular, producer_sequence records some message coordinates without declared coordinate FKs; dead_letter_message.original_offset is not a full source-message FK.
- report_dataset.request_id and report_result.request_id are each both PK and FK, enforcing at most one corresponding row per request, not requiring a pending request to have an output already.
- The final order_item relation has no line_total column. v_sales_lines calculates it; read migration 110 along with the original migration 060.
- report_run.status describes dataset preparation, while report_request.state describes individual output processing. These are different states.
- report_run.requested_by points to public.app_user. Current submissions use the configured reporting administrator identity, not separate per-browser-user requester attribution.
- Browser password/session credentials and broker application identities serve different purposes; their stored values must not appear on slides.
- The broker stores messages in PostgreSQL and uses PostgreSQL WAL. Reconcile the separate custom data-plane/WAL wording from Review 1 rather than claiming it is implemented.
- Inventory management is deferred. There are no implemented stock-balance or stock-movement tables; a SKU does not prove inventory management exists.

## Verification sources

- artifacts/database-schema-catalog.json: raw schema-only PostgreSQL catalog snapshot.
- db/sql and db/migrations: executable source; applied migrations must be read in order.
- artifacts/schema-constraint-demonstration.json: valid insertion plus rejected constraint cases, rolled back afterward.
- docs/PPT_REFERENCE.md: presentation-specific requirements and normalization examples.
