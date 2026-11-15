# Small logic additions and test changes used to create test-gap examples.
# Added code is inert until called; modified tests remain safe and deterministic.

MISSING_TEST_FEATURES = (
    (
        "notes_api",
        "notes_api/service.py",
        "def normalize_search_term(term: str) -> str:\n    return term.strip().casefold()",
        "def normalize_search_term",
    ),
    (
        "notes_api",
        "notes_api/auth.py",
        "def display_user_id(user_id: str) -> str:\n    return user_id.strip()",
        "def display_user_id",
    ),
    (
        "url_shortener",
        "shortener/service.py",
        "def code_prefix(code: str) -> str:\n    return code[:4]",
        "def code_prefix",
    ),
    (
        "csv_report",
        "report_tool/csv_data.py",
        "def row_category(row: dict[str, str]) -> str:\n    return row['category'].strip()",
        "def row_category",
    ),
)

TESTED_FEATURES = (
    (
        "notes_api",
        "notes_api/service.py",
        "def note_title_label(title: str) -> str:\n    return title.strip().title()",
        "def note_title_label",
        "notes_tests/test_notes.py",
        "def test_added_note_title_label():\n    from notes_api.service import note_title_label\n    assert note_title_label(' garden ') == 'Garden'",
    ),
    (
        "url_shortener",
        "shortener/service.py",
        "def code_label(code: str) -> str:\n    return f'short:{code}'",
        "def code_label",
        "shortener_tests/test_shortener.py",
        "def test_added_code_label():\n    from shortener.service import code_label\n    assert code_label('abc123') == 'short:abc123'",
    ),
    (
        "csv_report",
        "report_tool/aggregate.py",
        "def category_count(totals: dict[str, Decimal]) -> int:\n    return len(totals)",
        "def category_count",
        "report_tests/test_report.py",
        "def test_added_category_count():\n    from report_tool.aggregate import category_count\n    assert category_count({'sales': Decimal('1')}) == 1",
    ),
)

WEAKENED_ASSERTIONS = (
    (
        "notes_api",
        "notes_tests/test_notes.py",
        '    assert api.get("test-token", "alice", note_id) is not None',
        '    assert api.get("test-token", "alice", note_id) is not None or note_id > 0',
    ),
    (
        "url_shortener",
        "shortener_tests/test_shortener.py",
        "    assert code.isalnum()",
        "    assert isinstance(code, str)",
    ),
    (
        "csv_report",
        "report_tests/test_report.py",
        "    assert total_amount(rows) == 6.5",
        "    assert total_amount(rows) >= 0",
    ),
)

REMOVED_ASSERTIONS = (
    (
        "notes_api",
        "notes_tests/test_notes.py",
        '    assert not api.update("test-token", "bob", note_id, "Changed", "No.")',
        "    pass",
    ),
    ("url_shortener", "shortener_tests/test_shortener.py", "    assert code.isalnum()", "    pass"),
    (
        "csv_report",
        "report_tests/test_report.py",
        "    assert total_amount(rows) == 6.5",
        "    pass",
    ),
)

ASSERTION_REMOVAL_FEATURES = (
    (
        "notes_api",
        "notes_api/service.py",
        "def note_body_length(body: str) -> int:\n    return len(body)",
        "def note_body_length",
    ),
    (
        "url_shortener",
        "shortener/service.py",
        "def code_is_available(code: str) -> bool:\n    return bool(code)",
        "def code_is_available",
    ),
    (
        "csv_report",
        "report_tool/csv_data.py",
        "def report_row_count(rows: list[dict[str, str]]) -> int:\n    return len(rows)",
        "def report_row_count",
    ),
)
