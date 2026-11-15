# Passing behavior tests paired with benign sample-app changes.
# Synthetic API tokens and test destinations are isolated fixtures.

PRESUMED_CLEAN_TESTS = (
    (
        "notes_api",
        "notes_tests/test_notes.py",
        'def test_clean_notes_list_is_ordered(api):\n    first = api.create("test-token", "alice", "First", "A")\n    second = api.create("test-token", "alice", "Second", "B")\n    assert [item["id"] for item in api.list("test-token", "alice")] == [first, second]',
    ),
    (
        "notes_api",
        "notes_tests/test_notes.py",
        'def test_clean_notes_can_be_searched_by_title(api):\n    api.create("test-token", "alice", "Garden", "Seeds")\n    assert len(api.search("test-token", "alice", "Garden")) == 1',
    ),
    (
        "notes_api",
        "notes_tests/test_notes.py",
        'def test_clean_notes_can_be_updated(api):\n    note_id = api.create("test-token", "alice", "Draft", "One")\n    assert api.update("test-token", "alice", note_id, "Final", "Two")',
    ),
    (
        "notes_api",
        "notes_tests/test_notes.py",
        'def test_clean_notes_can_be_removed(api):\n    note_id = api.create("test-token", "alice", "Old", "Body")\n    assert api.delete("test-token", "alice", note_id)',
    ),
    (
        "notes_api",
        "notes_tests/test_notes.py",
        'def test_clean_note_search_is_empty_for_other_users(api):\n    api.create("test-token", "alice", "Private", "Text")\n    assert api.search("test-token", "bob", "Private") == []',
    ),
    (
        "notes_api",
        "notes_tests/test_notes.py",
        'def test_clean_note_search_respects_limit(api):\n    api.create("test-token", "alice", "A one", "x")\n    api.create("test-token", "alice", "A two", "x")\n    assert len(api.search("test-token", "alice", "A", limit=1)) == 1',
    ),
    (
        "url_shortener",
        "shortener_tests/test_shortener.py",
        'def test_clean_short_links_are_owner_scoped(api):\n    api.create("local-test-token", "alice", "https://example.test/a")\n    assert api.list("local-test-token", "bob") == []',
    ),
    (
        "url_shortener",
        "shortener_tests/test_shortener.py",
        'def test_clean_short_link_stats_start_at_zero(api):\n    api.create("local-test-token", "alice", "https://example.test/a")\n    assert api.stats("local-test-token", "alice") == {"links": 1, "visits": 0}',
    ),
    (
        "url_shortener",
        "shortener_tests/test_shortener.py",
        'def test_clean_short_link_can_be_removed(api):\n    code = api.create("local-test-token", "alice", "https://example.test/a")\n    assert api.delete("local-test-token", "alice", code)',
    ),
    (
        "url_shortener",
        "shortener_tests/test_shortener.py",
        'def test_clean_unknown_short_code_is_missing(api):\n    assert api.redirect_target("notfound") is None',
    ),
    (
        "url_shortener",
        "shortener_tests/test_shortener.py",
        'def test_clean_url_preview_uses_allowlist():\n    seen = []\n    title = preview_title("https://example.test/a", lambda url: seen.append(url) or "A", {"example.test"})\n    assert title == "A" and len(seen) == 1',
    ),
    (
        "url_shortener",
        "shortener_tests/test_shortener.py",
        'def test_clean_host_label_is_stable():\n    assert safe_host_label("https://example.test/a") == "example.test"',
    ),
    (
        "csv_report",
        "report_tests/test_report.py",
        'def test_clean_report_formats_empty_totals():\n    assert format_report({}) == "category,total\\n"',
    ),
    (
        "csv_report",
        "report_tests/test_report.py",
        'def test_clean_report_sorts_categories():\n    totals = totals_by_category([{"category": "b", "amount": "1"}, {"category": "a", "amount": "2"}])\n    assert list(totals) == ["b", "a"]',
    ),
    (
        "csv_report",
        "report_tests/test_report.py",
        'def test_clean_html_report_has_table_markup():\n    assert "<table>" in render_html_report({"sales": Decimal("1")})',
    ),
    (
        "csv_report",
        "report_tests/test_report.py",
        'def test_clean_csv_total_accepts_integer_amount():\n    assert total_amount([{"category": "x", "amount": "4"}]) == 4',
    ),
    (
        "csv_report",
        "report_tests/test_report.py",
        'def test_clean_csv_writer_keeps_header():\n    assert format_report({"sales": Decimal("2")}).startswith("category,total\\n")',
    ),
    (
        "csv_report",
        "report_tests/test_report.py",
        'def test_clean_output_path_has_report_suffix(tmp_path):\n    inputs = tmp_path / "input"\n    outputs = tmp_path / "reports"\n    inputs.mkdir()\n    (inputs / "month.csv").write_text("category,amount\\nsales,2\\n", encoding="utf-8")\n    assert build_report(inputs, outputs, "month").name == "month.report.csv"',
    ),
)
