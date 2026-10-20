"""Indian display conventions; stored facts and machine-readable exports stay numeric."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape


MONEY_COLUMNS = {
    "price", "unit_price", "catalogue_price", "line_total", "statement_total",
    "sales", "revenue", "running_sales", "previous_revenue", "amount",
    "total_sales", "total_revenue", "total_value",
}
COUNT_COLUMNS = {
    "quantity", "quantity_delta", "ledger_quantity", "reorder_level", "units",
    "orders", "customers", "runs", "completed", "active", "failed", "queued",
    "processing", "expected", "row_count", "saved_rows", "lines", "count",
    "valid", "rejected", "imported", "duplicate", "n",
}


def decimal_value(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def indian_number(value, places=None):
    number = decimal_value(value)
    if number is None:
        return str(value) if value is not None else "—"
    if places is not None:
        number = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    sign = "−" if number < 0 else ""
    whole, dot, fraction = format(abs(number), "f").partition(".")
    if len(whole) > 3:
        tail, head = whole[-3:], whole[:-3]
        groups = []
        while head:
            groups.insert(0, head[-2:])
            head = head[:-2]
        whole = ",".join(groups + [tail])
    return sign + whole + (dot + fraction if dot else "")


def number_labels(value, places=None):
    number = decimal_value(value)
    if number is None:
        return str(value) if value is not None else "—", None
    exact = indian_number(number, places)
    unit = None
    if abs(number) >= 10_000_000:
        divisor, unit = Decimal(10_000_000), "Cr."
    elif abs(number) >= 100_000:
        divisor, unit = Decimal(100_000), "Lakh"
    if unit:
        rounded = (number / divisor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        short = format(rounded, "f").rstrip("0").rstrip(".")
        return f"{short} {unit}", exact
    return exact, None


def number_text(value, places=None):
    main, exact = number_labels(value, places)
    return f"{main} ({exact})" if exact is not None else main


def display_cell(value, column=""):
    """Return escaped HTML; never abbreviate identity columns or numeric-looking names."""
    column = str(column).lower()
    if column.endswith(("_id", "_ref")) or column in {
        "sku", "line_number", "sales_rank", "version", "top_n", "month", "year",
    }:
        return escape(str(value)) if value is not None else "—"
    is_money = column in MONEY_COLUMNS
    is_numeric = isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
    if not (is_money or column in COUNT_COLUMNS or is_numeric):
        return escape(str(value)) if value is not None else "—"
    if decimal_value(value) is None:
        return escape(str(value)) if value is not None else "—"
    if column.endswith(("percent", "seconds")):
        return escape(indian_number(value))
    main, exact = number_labels(value, 2 if is_money else None)
    if exact is None:
        return escape(main)
    return (
        '<span class="number-value"><span>' + escape(main) + '</span>'
        '<small class="number-exact">(' + escape(exact) + ')</small></span>'
    )
