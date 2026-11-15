# Security seed patterns for credentials and injection flaws.
# Every clean snippet is taken from a sample application's checked-in source.

from evals.factory.template_types import CategoryPattern


def patterns() -> list[CategoryPattern]:
    """Return secret, SQL injection, and command injection patterns."""
    sql_before = """        row = connection.execute(
            "SELECT id, user_id, title, body, created_at FROM notes "
            "WHERE id = ? AND user_id = ?",
            (note_id, user_id),
        ).fetchone()"""
    sql_outputs = (
        """        row = connection.execute(
            f"SELECT id, user_id, title, body, created_at FROM notes "
            f"WHERE id = {note_id} AND user_id = '{user_id}'"
        ).fetchone()""",
        """        row = connection.execute(
            "SELECT id, user_id, title, body, created_at FROM notes "
            "WHERE id = " + str(note_id) + " AND user_id = '" + user_id + "'"
        ).fetchone()""",
        """        query = "SELECT * FROM notes WHERE id = %s AND user_id = '%s'" % (
        note_id, user_id
    )
        row = connection.execute(query).fetchone()""",
        """        query = "SELECT * FROM notes WHERE id = {} AND user_id = '{}'".format(
        note_id, user_id
    )
        row = connection.execute(query).fetchone()""",
    )
    sql_quotes = (
        """        f"WHERE id = {note_id} AND user_id = '{user_id}'\"""",
        """        "WHERE id = " + str(note_id) + " AND user_id = '" + user_id + "'\"""",
        """        query = "SELECT * FROM notes WHERE id = %s AND user_id = '%s'" % (""",
        """        query = "SELECT * FROM notes WHERE id = {} AND user_id = '{}'".format(""",
    )
    command_before = """    subprocess.run(
        [renderer, str(report_path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )"""
    command_outputs = (
        '    subprocess.run(f"{renderer} {report_path}", shell=True, check=True)',
        '    subprocess.run(renderer + " " + str(report_path), shell=True)',
        '    subprocess.run(f"{renderer} {report_path} 2>&1", shell=True)',
        '    subprocess.run(f"{renderer} {report_path}", shell=True, timeout=30)',
    )
    return [
        CategoryPattern(
            "hardcoded_secret",
            "notes_api",
            "notes_api/config.py",
            "critical",
            'api_token=os.environ.get("NOTES_API_TOKEN", ""),',
            (
                'api_token="synthetic-key-one",',
                'api_token="synthetic-key-two",',
                'api_token="synthetic-key-three",',
                'api_token="synthetic-key-four",',
            ),
            (
                'api_token="synthetic-key-one",',
                'api_token="synthetic-key-two",',
                'api_token="synthetic-key-three",',
                'api_token="synthetic-key-four",',
            ),
            "A credential is embedded directly in application source.",
            "Read the credential from a protected environment variable.",
        ),
        CategoryPattern(
            "sql_injection",
            "notes_api",
            "notes_api/db.py",
            "critical",
            sql_before,
            sql_outputs,
            sql_quotes,
            "User-controlled values are interpolated into a SQL statement.",
            "Keep placeholders and pass values separately to the database driver.",
        ),
        CategoryPattern(
            "command_injection",
            "csv_report",
            "report_tool/renderer.py",
            "critical",
            command_before,
            command_outputs,
            command_outputs,
            "A renderer command and path are combined into a shell command.",
            "Pass a fixed executable and an argument list with shell execution disabled.",
        ),
    ]
