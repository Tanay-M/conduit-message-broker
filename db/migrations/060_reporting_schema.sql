BEGIN;
CREATE SCHEMA reporting;
REVOKE ALL ON SCHEMA reporting FROM PUBLIC;

CREATE TABLE reporting.customer (
    customer_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_ref text NOT NULL UNIQUE,
    full_name text NOT NULL CHECK (length(trim(full_name)) > 0),
    email text NOT NULL UNIQUE,
    region text NOT NULL
);
CREATE TABLE reporting.product (
    product_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku text NOT NULL UNIQUE,
    product_name text NOT NULL,
    category text NOT NULL,
    catalogue_price numeric(12,2) NOT NULL CHECK (catalogue_price >= 0)
);
CREATE TABLE reporting.sales_order (
    order_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_ref text NOT NULL UNIQUE,
    customer_id bigint NOT NULL REFERENCES reporting.customer ON DELETE RESTRICT,
    ordered_at date NOT NULL,
    status text NOT NULL DEFAULT 'completed' CHECK (status IN ('completed','cancelled'))
);
CREATE INDEX sales_order_customer_date ON reporting.sales_order(customer_id, ordered_at);
CREATE INDEX sales_order_date ON reporting.sales_order(ordered_at);
CREATE TABLE reporting.order_item (
    order_id bigint NOT NULL REFERENCES reporting.sales_order ON DELETE RESTRICT,
    line_number integer NOT NULL CHECK (line_number > 0),
    product_id bigint NOT NULL REFERENCES reporting.product ON DELETE RESTRICT,
    quantity integer NOT NULL CHECK (quantity BETWEEN 1 AND 1000000),
    unit_price numeric(12,2) NOT NULL CHECK (unit_price >= 0),
    line_total numeric(20,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    PRIMARY KEY (order_id,line_number)
);
CREATE INDEX order_item_product ON reporting.order_item(product_id);

CREATE TABLE reporting.template_version (
    template_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL CHECK (code IN ('customer_statement','product_sales','monthly_sales')),
    version integer NOT NULL CHECK (version > 0),
    title text NOT NULL,
    sql_text text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(code,version)
);
CREATE TABLE reporting.report_run (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_key uuid NOT NULL UNIQUE,
    template_id bigint NOT NULL REFERENCES reporting.template_version ON DELETE RESTRICT,
    requested_by bigint NOT NULL REFERENCES app_user ON DELETE RESTRICT,
    customer_id bigint REFERENCES reporting.customer ON DELETE RESTRICT,
    start_date date NOT NULL,
    end_date date NOT NULL,
    top_n integer NOT NULL DEFAULT 10 CHECK (top_n BETWEEN 1 AND 100),
    bulk boolean NOT NULL DEFAULT false,
    status text NOT NULL DEFAULT 'preparing' CHECK (status IN ('preparing','ready','failed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    prepared_at timestamptz,
    error text,
    CHECK (start_date < end_date),
    CHECK (end_date - start_date <= 3660)
);
CREATE TABLE reporting.report_request (
    request_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES reporting.report_run ON DELETE RESTRICT,
    subject_key text NOT NULL,
    customer_id bigint REFERENCES reporting.customer ON DELETE RESTRICT,
    state text NOT NULL DEFAULT 'queued' CHECK (state IN ('queued','processing','completed','failed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    last_error text,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    UNIQUE(run_id,subject_key)
);
CREATE INDEX request_run_state ON reporting.report_request(run_id,state);
CREATE TABLE reporting.report_dataset (
    request_id uuid PRIMARY KEY REFERENCES reporting.report_request ON DELETE RESTRICT,
    rows jsonb NOT NULL CHECK (jsonb_typeof(rows) = 'array'),
    captured_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE reporting.report_result (
    request_id uuid PRIMARY KEY REFERENCES reporting.report_request ON DELETE RESTRICT,
    csv_path text NOT NULL UNIQUE,
    html_path text NOT NULL UNIQUE,
    csv_sha256 text NOT NULL CHECK (csv_sha256 ~ '^[0-9a-f]{64}$'),
    html_sha256 text NOT NULL CHECK (html_sha256 ~ '^[0-9a-f]{64}$'),
    row_count integer NOT NULL CHECK (row_count >= 0),
    worker_name text NOT NULL,
    sql_seconds double precision NOT NULL CHECK (sql_seconds >= 0),
    render_seconds double precision NOT NULL CHECK (render_seconds >= 0),
    completed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE reporting.report_audit (
    audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id uuid NOT NULL REFERENCES reporting.report_request ON DELETE RESTRICT,
    old_state text,
    new_state text NOT NULL,
    event_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX report_audit_request ON reporting.report_audit(request_id,event_at);

CREATE FUNCTION reporting.audit_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO reporting.report_audit(request_id,old_state,new_state)
    VALUES(NEW.request_id, CASE WHEN TG_OP='INSERT' THEN NULL ELSE OLD.state END, NEW.state);
    RETURN NEW;
END $$;
CREATE TRIGGER reporting_request_insert AFTER INSERT ON reporting.report_request
FOR EACH ROW EXECUTE FUNCTION reporting.audit_state();
CREATE TRIGGER reporting_request_state AFTER UPDATE OF state ON reporting.report_request
FOR EACH ROW WHEN (OLD.state IS DISTINCT FROM NEW.state) EXECUTE FUNCTION reporting.audit_state();

CREATE FUNCTION reporting.prevent_history_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Historical template/dataset rows are immutable' USING ERRCODE='23514'; END $$;
CREATE TRIGGER immutable_template BEFORE UPDATE OR DELETE ON reporting.template_version
FOR EACH ROW EXECUTE FUNCTION reporting.prevent_history_change();
CREATE TRIGGER immutable_dataset BEFORE UPDATE OR DELETE ON reporting.report_dataset
FOR EACH ROW EXECUTE FUNCTION reporting.prevent_history_change();

CREATE VIEW reporting.v_sales_lines AS
SELECT c.customer_id,c.customer_ref,c.full_name,c.region,
       o.order_id,o.order_ref,o.ordered_at,
       i.line_number,p.sku,p.product_name,p.category,i.quantity,i.unit_price,i.line_total
FROM reporting.customer c
JOIN reporting.sales_order o ON o.customer_id=c.customer_id
JOIN reporting.order_item i ON i.order_id=o.order_id
JOIN reporting.product p ON p.product_id=i.product_id
WHERE o.status='completed';

CREATE VIEW reporting.v_run_progress AS
SELECT r.run_id,t.code,t.version,r.status AS preparation_status,r.created_at,r.prepared_at,
       count(q.request_id) AS expected,
       count(*) FILTER (WHERE q.state='queued') AS queued,
       count(*) FILTER (WHERE q.state='processing') AS processing,
       count(*) FILTER (WHERE q.state='completed') AS completed,
       count(*) FILTER (WHERE q.state='failed') AS failed,
       max(q.completed_at) AS last_completion
FROM reporting.report_run r JOIN reporting.template_version t USING(template_id)
LEFT JOIN reporting.report_request q USING(run_id)
GROUP BY r.run_id,t.code,t.version;

CREATE MATERIALIZED VIEW reporting.mv_monthly_sales AS
SELECT date_trunc('month',ordered_at)::date AS month,category,
       sum(quantity) AS units,sum(line_total) AS sales
FROM reporting.v_sales_lines GROUP BY 1,2;
CREATE UNIQUE INDEX monthly_sales_key ON reporting.mv_monthly_sales(month,category);

COMMENT ON TABLE reporting.report_dataset IS 'Persisted report content, deliberately retained beyond MVCC transaction lifetime';
COMMENT ON COLUMN reporting.order_item.unit_price IS 'Historical sale-time price, independent of current catalogue price';
COMMIT;
