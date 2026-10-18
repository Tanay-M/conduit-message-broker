"""Atomic inventory posting with sales integration and ledger reconciliation."""

from datetime import date
from decimal import Decimal, InvalidOperation

from .service import connect

INVENTORY_SQL = "SELECT * FROM reporting.v_inventory ORDER BY low_stock DESC,sku"


def post(
    sku,
    kind,
    quantity,
    reference,
    note="",
    actor="admin",
    customer_ref=None,
    unit_price=None,
    posted_on=None,
):
    if kind not in ("receipt", "sale") or not 1 <= int(quantity) <= 1000000:
        raise ValueError("Choose receipt/sale and a quantity from 1 to 1,000,000")
    if not reference.strip() or len(reference) > 100 or len(note) > 500:
        raise ValueError(
            "A reference of at most 100 characters and note of at most 500 characters are required"
        )
    price = None
    if kind == "sale":
        try:
            price = Decimal(str(unit_price))
            if (
                not price.is_finite()
                or price < 0
                or price != price.quantize(Decimal(".01"))
            ):
                raise ValueError()
        except (ValueError, InvalidOperation):
            raise ValueError(
                "Enter a nonnegative sale price with at most two decimals"
            ) from None
    with connect() as conn, conn.transaction():
        product = conn.execute(
            "SELECT product_id FROM reporting.product WHERE sku=%s", (sku.strip(),)
        ).fetchone()
        if product is None:
            raise ValueError("Unknown SKU; choose an existing product")
        customer = None
        if kind == "sale":
            customer = conn.execute(
                "SELECT customer_id FROM reporting.customer WHERE customer_ref=%s",
                (customer_ref,),
            ).fetchone()
            if customer is None:
                raise ValueError("A sale requires an existing customer reference")
        result = conn.execute(
            "SELECT reporting.post_stock(%s,%s,%s,%s,%s,%s,%s,%s,%s) AS movement_id",
            (
                product["product_id"],
                kind,
                int(quantity),
                reference.strip(),
                note,
                actor,
                customer["customer_id"] if customer else None,
                price,
                date.fromisoformat(str(posted_on)) if posted_on else date.today(),
            ),
        ).fetchone()
        return result["movement_id"]


def reorder(sku, level):
    level = int(level)
    if not 0 <= level <= 1000000:
        raise ValueError("Reorder level must be from 0 to 1,000,000")
    with connect() as conn, conn.transaction():
        product = conn.execute(
            "SELECT product_id FROM reporting.product WHERE sku=%s", (sku.strip(),)
        ).fetchone()
        if not product:
            raise ValueError("Unknown SKU")
        conn.execute(
            "INSERT INTO reporting.inventory_balance(product_id,reorder_level) VALUES(%s,%s) "
            "ON CONFLICT(product_id) DO UPDATE SET reorder_level=EXCLUDED.reorder_level,updated_at=now()",
            (product["product_id"], level),
        )


def dashboard():
    with connect() as conn:
        return {
            "rows": conn.execute(INVENTORY_SQL).fetchall(),
            "products": conn.execute(
                "SELECT sku,product_name,catalogue_price FROM reporting.product ORDER BY sku LIMIT 200"
            ).fetchall(),
            "movements": conn.execute(
                "SELECT m.*,p.sku FROM reporting.stock_movement m JOIN reporting.product p USING(product_id) ORDER BY movement_id DESC LIMIT 40"
            ).fetchall(),
            "sql": INVENTORY_SQL,
        }
