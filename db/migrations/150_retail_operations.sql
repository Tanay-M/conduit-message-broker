BEGIN;

CREATE TABLE reporting.inventory_balance (
 product_id bigint PRIMARY KEY REFERENCES reporting.product ON DELETE RESTRICT,
 quantity integer NOT NULL DEFAULT 0 CHECK (quantity >= 0),
 reorder_level integer NOT NULL DEFAULT 10 CHECK (reorder_level >= 0),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE reporting.stock_movement (
 movement_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 product_id bigint NOT NULL REFERENCES reporting.product ON DELETE RESTRICT,
 kind text NOT NULL CHECK (kind IN ('receipt','sale')),
 quantity_delta integer NOT NULL CHECK (quantity_delta <> 0),
 reference text NOT NULL UNIQUE CHECK (length(trim(reference)) BETWEEN 1 AND 100),
 note text NOT NULL DEFAULT '' CHECK (length(note) <= 500),
 actor text NOT NULL,
 customer_id bigint REFERENCES reporting.customer ON DELETE RESTRICT,
 unit_price numeric(12,2),
 order_id bigint UNIQUE REFERENCES reporting.sales_order ON DELETE RESTRICT,
 posted_on date NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK ((kind='receipt' AND quantity_delta>0 AND order_id IS NULL AND customer_id IS NULL AND unit_price IS NULL)
     OR (kind='sale' AND quantity_delta<0 AND order_id IS NOT NULL AND customer_id IS NOT NULL
         AND unit_price IS NOT NULL AND unit_price>=0 AND unit_price<=9999999999.99))
);
CREATE INDEX stock_movement_product_time ON reporting.stock_movement(product_id,created_at DESC);
CREATE FUNCTION reporting.protect_stock_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Posted stock movements are append-only' USING ERRCODE='23514'; END $$;
CREATE TRIGGER stock_history_immutable BEFORE UPDATE OR DELETE ON reporting.stock_movement
 FOR EACH ROW EXECUTE FUNCTION reporting.protect_stock_history();

CREATE FUNCTION reporting.post_stock(p_product bigint,p_kind text,p_quantity integer,p_reference text,
 p_note text,p_actor text,p_customer bigint DEFAULT NULL,p_price numeric DEFAULT NULL,p_date date DEFAULT CURRENT_DATE)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE existing reporting.stock_movement; balance integer; sale_id bigint; movement bigint;
BEGIN
 IF p_kind NOT IN ('receipt','sale') OR p_kind IS NULL OR p_quantity IS NULL OR p_quantity NOT BETWEEN 1 AND 1000000
    OR p_reference IS NULL OR length(trim(p_reference)) NOT BETWEEN 1 AND 100 OR p_date IS NULL THEN
   RAISE EXCEPTION 'Choose a valid operation, quantity, reference and date' USING ERRCODE='23514';
 END IF;
 IF p_kind='sale' AND (p_customer IS NULL OR p_price IS NULL OR p_price<0 OR p_price>9999999999.99 OR p_price<>round(p_price,2)) THEN
   RAISE EXCEPTION 'A sale requires a customer and a nonnegative price with at most two decimals' USING ERRCODE='23514';
 END IF;
 IF p_kind='receipt' AND (p_customer IS NOT NULL OR p_price IS NOT NULL) THEN
   RAISE EXCEPTION 'Receipts do not take a customer or sale price' USING ERRCODE='23514';
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('stock-reference:'||p_reference,0));
 SELECT * INTO existing FROM reporting.stock_movement WHERE reference=p_reference;
 IF FOUND THEN
   IF (existing.product_id,existing.kind,abs(existing.quantity_delta),existing.note,existing.actor,
       existing.customer_id,existing.unit_price,existing.posted_on)
      IS DISTINCT FROM (p_product,p_kind,p_quantity,COALESCE(p_note,''),p_actor,p_customer,p_price,p_date) THEN
     RAISE EXCEPTION 'Reference already used with different details' USING ERRCODE='23505';
   END IF;
   RETURN existing.movement_id;
 END IF;
 INSERT INTO reporting.inventory_balance(product_id) VALUES(p_product) ON CONFLICT DO NOTHING;
 SELECT quantity INTO balance FROM reporting.inventory_balance WHERE product_id=p_product FOR UPDATE;
 IF p_kind='sale' AND balance<p_quantity THEN
   RAISE EXCEPTION 'Insufficient stock: % available, % requested',balance,p_quantity USING ERRCODE='23514';
 END IF;
 IF p_kind='sale' THEN
   INSERT INTO reporting.sales_order(order_ref,customer_id,ordered_at,status)
   VALUES('STOCK-'||p_reference,p_customer,p_date,'completed') RETURNING order_id INTO sale_id;
   INSERT INTO reporting.order_item(order_id,line_number,product_id,quantity,unit_price)
   VALUES(sale_id,1,p_product,p_quantity,p_price);
 END IF;
 UPDATE reporting.inventory_balance SET quantity=quantity+CASE WHEN p_kind='receipt' THEN p_quantity ELSE -p_quantity END,
 updated_at=now() WHERE product_id=p_product;
 INSERT INTO reporting.stock_movement(product_id,kind,quantity_delta,reference,note,actor,customer_id,unit_price,order_id,posted_on)
 VALUES(p_product,p_kind,CASE WHEN p_kind='receipt' THEN p_quantity ELSE -p_quantity END,p_reference,COALESCE(p_note,''),p_actor,
 p_customer,p_price,sale_id,p_date) RETURNING movement_id INTO movement;
 RETURN movement;
END $$;

CREATE VIEW reporting.v_inventory AS
SELECT p.product_id,p.sku,p.product_name,p.category,p.catalogue_price,b.quantity,b.reorder_level,b.updated_at,
 b.quantity<=b.reorder_level AS low_stock,
 COALESCE(m.net,0) AS ledger_quantity,b.quantity=COALESCE(m.net,0) AS reconciled
FROM reporting.inventory_balance b JOIN reporting.product p USING(product_id)
LEFT JOIN (SELECT product_id,sum(quantity_delta) AS net FROM reporting.stock_movement GROUP BY product_id) m USING(product_id);

CREATE TABLE reporting.import_batch (
 batch_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), filename text NOT NULL,
 file_sha256 text NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
 headers jsonb NOT NULL CHECK (jsonb_typeof(headers)='array'),
 mapping jsonb NOT NULL CHECK (jsonb_typeof(mapping)='object'),
 mapping_source text NOT NULL, actor text NOT NULL,
 state text NOT NULL DEFAULT 'preview' CHECK (state IN ('preview','committed')),
 created_at timestamptz NOT NULL DEFAULT now(), committed_at timestamptz
);
CREATE TABLE reporting.import_row (
 batch_id uuid NOT NULL REFERENCES reporting.import_batch ON DELETE RESTRICT,
 row_number integer NOT NULL CHECK (row_number>0),
 raw jsonb NOT NULL CHECK (jsonb_typeof(raw)='object'),
 cleaned jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(cleaned)='object'),
 errors jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(errors)='array'),
 state text NOT NULL CHECK (state IN ('valid','rejected','imported','duplicate')),
 PRIMARY KEY(batch_id,row_number)
);
CREATE INDEX import_row_batch_state ON reporting.import_row(batch_id,state);
CREATE TABLE reporting.assistant_request (
 request_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), actor text NOT NULL,
 prompt text NOT NULL CHECK (length(prompt) BETWEEN 1 AND 2000),
 interpretation jsonb NOT NULL, sql_text text NOT NULL, parameters jsonb NOT NULL,
 source text NOT NULL, model text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE reporting.analysis_run (
 analysis_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), actor text NOT NULL,
 start_date date NOT NULL,end_date date NOT NULL CHECK (end_date>start_date),
 facts jsonb NOT NULL, narrative text NOT NULL, source text NOT NULL, model text,
 created_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
