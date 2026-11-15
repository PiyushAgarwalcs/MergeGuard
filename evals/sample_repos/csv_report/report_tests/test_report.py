# Examples of CSV report behavior and path safety.
# Temporary directories keep file operations isolated from the working tree.

import subprocess
from decimal import Decimal
from pathlib import Path

import pytest
from report_tool.aggregate import format_report, totals_by_category
from report_tool.csv_data import read_rows, total_amount
from report_tool.html_report import render_html_report
from report_tool.paths import contained_path
from report_tool.renderer import render
from report_tool.service import build_report


def test_read_and_total_csv_rows(tmp_path: Path) -> None:
    """CSV inputs produce correctly parsed rows and a numeric total."""
    source = tmp_path / "sales.csv"
    source.write_text("category,amount\nbooks,2.50\nfood,4\n", encoding="utf-8")

    rows = read_rows(source)

    assert total_amount(rows) == 6.5


def test_aggregate_report_is_sorted_and_uses_two_decimals() -> None:
    """Category aggregation has deterministic presentation."""
    totals = totals_by_category(
        [{"category": "z", "amount": "1"}, {"category": "a", "amount": "2.5"}]
    )

    assert totals == {"z": Decimal(1), "a": Decimal("2.5")}
    assert format_report(totals) == "category,total\na,2.50\nz,1.00\n"


def test_report_writes_to_output_directory(tmp_path: Path) -> None:
    """The service builds a report from a named CSV."""
    inputs = tmp_path / "input"
    outputs = tmp_path / "reports"
    inputs.mkdir()
    (inputs / "month.csv").write_text("category,amount\nrent,10\n", encoding="utf-8")

    report = build_report(inputs, outputs, "month")

    assert report.read_text(encoding="utf-8") == "category,total\nrent,10.00\n"


def test_input_name_cannot_escape_directory(tmp_path: Path) -> None:
    """Names with path components are refused."""
    with pytest.raises(ValueError):
        contained_path(tmp_path, "../private", ".csv")


def test_renderer_uses_argument_list_and_propagates_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Renderer failures remain visible to the caller."""
    captured: list[list[str]] = []

    def fake_run(arguments: list[str], **_: object) -> None:
        captured.append(arguments)

    monkeypatch.setattr(subprocess, "run", fake_run)
    report_path = tmp_path / "report with spaces.csv"
    render("safe-renderer", report_path)

    assert captured == [["safe-renderer", str(report_path)]]

    def fail_run(*_: object, **__: object) -> None:
        raise subprocess.CalledProcessError(1, ["renderer"])

    monkeypatch.setattr(subprocess, "run", fail_run)
    with pytest.raises(subprocess.CalledProcessError):
        render("safe-renderer", report_path)


def test_csv_rejects_missing_required_columns(tmp_path: Path) -> None:
    """Malformed inputs produce a descriptive validation error."""
    source = tmp_path / "bad.csv"
    source.write_text("name,value\nx,1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="category and amount"):
        read_rows(source)


def test_csv_rejects_invalid_amount_with_row_number(tmp_path: Path) -> None:
    """Malformed numeric input points to its source row."""
    source = tmp_path / "bad_amount.csv"
    source.write_text("category,amount\nfood,nope\n", encoding="utf-8")

    with pytest.raises(ValueError, match="row 2"):
        read_rows(source)


def test_csv_rejects_empty_data_file(tmp_path: Path) -> None:
    """A header without records is not treated as an empty successful report."""
    source = tmp_path / "empty.csv"
    source.write_text("category,amount\n", encoding="utf-8")

    with pytest.raises(ValueError, match="at least one"):
        read_rows(source)


def test_csv_rejects_non_finite_report_values() -> None:
    """NaN cannot silently propagate into generated totals."""
    with pytest.raises(ValueError, match="Non-finite"):
        totals_by_category([{"category": "balance", "amount": "NaN"}])


def test_report_escapes_spreadsheet_formula_categories() -> None:
    """Untrusted category labels are emitted as text rather than formulas."""
    totals = totals_by_category([{"category": "=SUM(A1:A2)", "amount": "1"}])

    assert format_report(totals) == "category,total\n'=SUM(A1:A2),1.00\n"


def test_renderer_is_skipped_when_not_configured(tmp_path: Path) -> None:
    """An empty renderer setting disables process execution."""
    render("", tmp_path / "report.csv")


def test_csv_writer_quotes_category_commas() -> None:
    """Category values containing commas stay in one CSV column."""
    totals = totals_by_category([{"category": "food, drinks", "amount": "3"}])

    assert format_report(totals) == 'category,total\n"food, drinks",3.00\n'


def test_report_replaces_existing_file_without_leaving_temp_files(tmp_path: Path) -> None:
    """Repeated runs atomically replace a report in place."""
    inputs = tmp_path / "input"
    outputs = tmp_path / "reports"
    inputs.mkdir()
    outputs.mkdir()
    (inputs / "month.csv").write_text("category,amount\nrent,10\n", encoding="utf-8")
    target = outputs / "month.report.csv"
    target.write_text("old report\n", encoding="utf-8")

    report = build_report(inputs, outputs, "month")

    assert report == target
    assert target.read_text(encoding="utf-8") == "category,total\nrent,10.00\n"
    assert not (outputs / "month.report.tmp").exists()


def test_report_removes_temporary_file_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed replacement does not leave a partial report behind."""
    from report_tool import service

    inputs = tmp_path / "input"
    outputs = tmp_path / "reports"
    inputs.mkdir()
    (inputs / "month.csv").write_text("category,amount\nrent,10\n", encoding="utf-8")

    def fail_replace(*_: object) -> None:
        raise OSError("replacement failed")

    monkeypatch.setattr(service.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replacement failed"):
        build_report(inputs, outputs, "month")

    assert not (outputs / "month.report.tmp").exists()


def test_csv_rejects_rows_with_additional_columns(tmp_path: Path) -> None:
    """Extra cells are rejected instead of being silently discarded."""
    source = tmp_path / "extra.csv"
    source.write_text("category,amount\nfood,2,unexpected\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid columns"):
        read_rows(source)


def test_csv_writer_preserves_quotes_and_newlines_in_category() -> None:
    """CSV quoting keeps unusual category text inside one record."""
    totals = totals_by_category([{"category": 'food "special"\nitems', "amount": "1"}])
    output = format_report(totals)

    assert output.startswith("category,total\n")
    assert 'food ""special""\nitems' in output


def test_input_path_requires_a_plain_name(tmp_path: Path) -> None:
    """Absolute input paths cannot replace the configured directory."""
    with pytest.raises(ValueError):
        contained_path(tmp_path, str(tmp_path / "outside"), ".csv")


def test_html_report_escapes_untrusted_category_labels() -> None:
    """HTML output encodes markup supplied as a category value."""
    totals = totals_by_category([{"category": '<img src=x onerror="run()">', "amount": "1"}])

    html = render_html_report(totals)

    assert "&lt;img" in html
    assert "<img" not in html
