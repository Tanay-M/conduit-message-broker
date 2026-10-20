import csv
import io
from decimal import Decimal

import pytest

from reporting.formatting import display_cell, indian_number, number_labels
from reporting.render import documents


@pytest.mark.parametrize("value,expected", [
    (0, "0"), (1000, "1,000"), (100000, "1,00,000"),
    (21601654, "2,16,01,654"), (Decimal("17493.00"), "17,493.00"),
    (-1234567, "−12,34,567"),
])
def test_indian_grouping(value, expected):
    assert indian_number(value) == expected


def test_compact_rounding_keeps_exact_value():
    assert number_labels(21601654) == ("2.16 Cr.", "2,16,01,654")
    assert number_labels(20000000) == ("2 Cr.", "2,00,00,000")
    assert number_labels(123456, 2) == ("1.23 Lakh", "1,23,456.00")
    html = display_cell("21601654", "revenue")
    assert "2.16 Cr." in html and "2,16,01,654.00" in html


def test_identities_names_and_unsafe_text_are_not_formatted_as_amounts():
    assert display_cell(12345678, "order_id") == "12345678"
    assert display_cell("12345678", "customer_ref") == "12345678"
    assert display_cell("12345678", "product_name") == "12345678"
    assert display_cell("<script>alert(1)</script>", "product_name").startswith("&lt;script&gt;")
    assert "Cr." not in display_cell(125000, "change_percent")


def test_generated_html_is_formatted_but_csv_remains_numeric():
    report = {
        "rows": [{"order_id": 12345678, "line_total": "21601654.00", "product_name": "<Keyboard>"}],
        "title": "Statement", "run_id": "test", "version": 1,
        "start_date": "2026-01-01", "end_date": "2027-01-01",
    }
    result = documents(report)
    html = result["html"].decode()
    assert "2.16 Cr." in html and "2,16,01,654.00" in html
    assert "&lt;Keyboard&gt;" in html and "12345678" in html
    row = next(csv.DictReader(io.StringIO(result["csv"].decode())))
    assert row["line_total"] == "21601654.00" and row["order_id"] == "12345678"
