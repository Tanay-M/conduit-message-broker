from datetime import date
from decimal import Decimal
from starlette.requests import Request

from server.app.webui.reports import templates


def render(page, **values):
    return templates.get_template(f"pages/{page}.html").render(
        request=Request({"type": "http", "method": "GET", "path": "/", "headers": []}),
        ctx={"mode": "admin", "owner_username": "sysadmin"}, active=page,
        error=None, **values,
    )


def test_forms_have_no_ai_controls_or_supported_question_panel():
    imports = render("imports", batches=[])
    assistant = render("assistant", prompt="", record=None, result=None)
    analysis = render("analysis", start="2026-01-01", end="2027-01-01", result=None)
    for html in [imports, assistant, analysis]:
        assert 'name="use_ai"' not in html
        assert 'AI is not configured' not in html
    assert "Supported questions" not in assistant and "Gemini interpretation" not in assistant
    assert "Use Gemini to suggest" not in imports and "AI explanation" not in analysis


def test_analysis_shows_subtle_ai_credit_only_for_successful_insights():
    result = {"facts": {"totals": {"revenue": Decimal("21601654"), "orders": 120000,
        "customers": 1000, "units": 4000}, "categories": [], "months": [], "alerts": [], "low_stock": []},
        "narrative": "Summary", "analysis_id": "test", "sql": {}, "ai_insights": True}
    html = render("analysis", start="2026-01-01", end="2027-01-01", result=result)
    assert "2.16 Cr." in html and "2,16,01,654.00" in html
    assert 'class="table-note">With AI insights' in html
    result["ai_insights"] = False
    assert "With AI insights" not in render("analysis", start="2026-01-01", end="2027-01-01", result=result)
