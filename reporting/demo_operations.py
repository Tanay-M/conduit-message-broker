"""Small, named retail fixtures for the final-review workflow. Additive, repeat-safe."""

from . import inventory
from .service import connect


def prepare():
    products = [
        ("DEMO-KEYBOARD", "Wireless Keyboard", "Accessories", "2499.00", 50),
        ("DEMO-MOUSE", "Wireless Mouse", "Accessories", "799.00", 8),
        ("DEMO-HUB", "USB-C Hub", "Accessories", "1499.00", 20),
    ]
    with connect() as conn, conn.transaction():
        conn.execute(
            "INSERT INTO reporting.customer(customer_ref,full_name,email,region) VALUES('REVIEW-001','Northstar Office Supplies','northstar@example.test','South') ON CONFLICT(customer_ref) DO NOTHING"
        )
        for sku, name, category, price, quantity in products:
            conn.execute(
                "INSERT INTO reporting.product(sku,product_name,category,catalogue_price) VALUES(%s,%s,%s,%s) ON CONFLICT(sku) DO NOTHING",
                (sku, name, category, price),
            )
    for sku, name, category, price, quantity in products:
        inventory.post(
            sku,
            "receipt",
            quantity,
            "OPENING-" + sku,
            "Explicit final-review opening receipt",
            "demo-setup",
            posted_on="2026-10-01",
        )
    return "Prepared REVIEW-001 and three named products with explicit opening receipts. No historical sales or existing stock were reset."


if __name__ == "__main__":
    print(prepare())
