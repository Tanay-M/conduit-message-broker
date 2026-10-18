"""Deterministic, additive sales fixtures. Existing rows are never reset."""

import argparse
import json
import time

from .service import connect


def seed(customers=20, orders_per_customer=5):
    if not 1 <= customers <= 100000 or not 1 <= orders_per_customer <= 100:
        raise ValueError("Choose 1..100000 customers and 1..100 orders per customer")
    started = time.perf_counter()
    with connect() as conn, conn.transaction():
        conn.execute(
            """INSERT INTO reporting.customer(customer_ref,full_name,email,region)
            SELECT 'DEMO-'||lpad(g::text,6,'0'),'Customer '||g,'customer'||g||'@example.test',
                   (ARRAY['North','South','East','West'])[1+mod(g,4)]
            FROM generate_series(1,%s) g ON CONFLICT(customer_ref) DO NOTHING""",
            (customers,),
        )
        conn.execute("""INSERT INTO reporting.product(sku,product_name,category,catalogue_price)
            SELECT 'SKU-'||g,'Product '||g,(ARRAY['Office','Home','Electronics'])[1+(g%3)],(g*25)::numeric
            FROM generate_series(1,30) g ON CONFLICT(sku) DO NOTHING""")
        conn.execute(
            """INSERT INTO reporting.sales_order(order_ref,customer_id,ordered_at)
            SELECT c.customer_ref||'-'||n,c.customer_id,date '2026-01-01'+mod(n*7+c.customer_id::int,270)
            FROM reporting.customer c CROSS JOIN generate_series(1,%s) n
            WHERE c.customer_ref BETWEEN 'DEMO-000001' AND 'DEMO-'||lpad(%s::text,6,'0')
            ON CONFLICT(order_ref) DO NOTHING""",
            (orders_per_customer, customers),
        )
        conn.execute("""INSERT INTO reporting.order_item(order_id,line_number,product_id,quantity,unit_price)
            SELECT o.order_id,n,p.product_id,1+((o.order_id+n)%4),p.catalogue_price
            FROM reporting.sales_order o CROSS JOIN generate_series(1,3) n
            JOIN reporting.product p ON p.sku='SKU-'||(1+((o.order_id+n)%30))
            WHERE o.order_ref LIKE 'DEMO-%%' ON CONFLICT(order_id,line_number) DO NOTHING""")
        conn.execute("REFRESH MATERIALIZED VIEW reporting.mv_monthly_sales")
        totals = conn.execute("""SELECT (SELECT count(*) FROM reporting.customer) AS customers,
            (SELECT count(*) FROM reporting.sales_order) AS orders,
            (SELECT count(*) FROM reporting.order_item) AS items""").fetchone()
    with connect() as conn:
        conn.execute(
            "ANALYZE reporting.customer,reporting.product,reporting.sales_order,reporting.order_item"
        )
    return {**totals, "seconds": round(time.perf_counter() - started, 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", type=int, default=20)
    parser.add_argument(
        "--orders", type=int, default=5, help="Orders per seeded customer"
    )
    args = parser.parse_args()
    print(json.dumps(seed(args.customers, args.orders)))


if __name__ == "__main__":
    main()
