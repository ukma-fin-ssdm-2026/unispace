"""
Тести скрипта перевірки простежуваності (scripts/check_traceability.py).

Примітка щодо використання ШІ: тести згенеровано ШІ (Claude), переглянуто автором PR.
"""

import textwrap

from scripts.check_traceability import check, collect_test_marks, main, read_requirement_ids

RTM = """
| ID | Опис |
| :--- | :--- |
| **US-01** | Фільтрація аудиторій |
| **SEC-001** | Заборона для студентів |
"""


def write(path, text):
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def make_project(tmp_path, test_source, exceptions=""):
    tmp_path.mkdir(parents=True, exist_ok=True)
    rtm = write(tmp_path / "rtm.md", RTM)
    tests_dir = tmp_path / "api" / "tests"
    tests_dir.mkdir(parents=True)
    write(tests_dir / "test_sample.py", test_source)
    exceptions_file = write(tmp_path / "traceability.toml", exceptions)
    return ["--rtm", str(rtm), "--tests", str(tests_dir), "--exceptions", str(exceptions_file)]


def test_requirement_ids_are_read_from_bold_first_column(tmp_path):
    # Arrange
    rtm = write(tmp_path / "rtm.md", RTM + "| FR-010 | не жирний ID - не рядок вимоги |\n")

    # Act
    ids = read_requirement_ids(rtm)

    # Assert
    assert ids == ["US-01", "SEC-001"]


def test_marks_are_collected_from_function_class_and_pytestmark(tmp_path):
    # Arrange
    tests_dir = tmp_path / "api" / "tests"
    tests_dir.mkdir(parents=True)
    write(
        tests_dir / "test_sample.py",
        """
        import pytest

        pytestmark = [pytest.mark.django_db, pytest.mark.req("US-01")]

        @pytest.mark.req("SEC-001")
        def test_function():
            pass

        @pytest.mark.req("SEC-001")
        class RoomTests:
            def test_method(self):
                pass

        def helper():
            pass
        """,
    )

    # Act
    marks = collect_test_marks(tests_dir, base_dir=tmp_path)

    # Assert
    assert marks == {
        "api/tests/test_sample.py::test_function": {"US-01", "SEC-001"},
        "api/tests/test_sample.py::RoomTests::test_method": {"US-01", "SEC-001"},
    }


def test_requirement_without_tests_is_a_gap():
    report = check(["US-01", "SEC-001"], {"t.py::test_a": {"US-01"}}, {}, {})

    assert report.errors == ["Вимога SEC-001 не має жодного тесту"]


def test_test_without_requirement_is_a_gap():
    report = check(["US-01"], {"t.py::test_a": {"US-01"}, "t.py::test_b": set()}, {}, {})

    assert report.errors == ["Тест t.py::test_b не посилається на жодну вимогу"]


def test_unknown_requirement_id_in_mark_is_reported():
    report = check(["US-01"], {"t.py::test_a": {"US-01", "US-99"}}, {}, {})

    assert report.errors == ["Тест t.py::test_a посилається на US-99, якого немає в rtm.md"]


def test_documented_exceptions_close_the_gaps():
    # Arrange: вимога ще не реалізована, клас тестів перевіряє не вимогу RTM
    tests = {"t.py::test_a": {"US-01"}, "t.py::SchemaTests::test_schema": set()}

    # Act
    report = check(["US-01", "SEC-001"], tests, {"SEC-001": "ще не реалізовано"}, {"t.py::SchemaTests": "QA-05"})

    # Assert
    assert report.errors == []


def test_stale_requirement_exception_is_reported():
    report = check(["US-01"], {"t.py::test_a": {"US-01"}}, {"US-01": "ще не реалізовано"}, {})

    assert report.errors == ["Виняток для US-01 застарів: вимога вже має тести, приберіть її з винятків"]


def test_stale_and_dangling_test_exceptions_are_reported():
    # Arrange
    tests = {"t.py::test_a": {"US-01"}}
    test_exceptions = {"t.py::test_a": "вже має мітку", "t.py::Missing": "такого класу немає"}

    # Act
    report = check(["US-01"], tests, {}, test_exceptions)

    # Assert
    assert report.errors == [
        "Виняток для тестів t.py::Missing ні до чого не відноситься, приберіть його",
        "Виняток для тестів t.py::test_a застарів: тести вже мають мітки вимог",
    ]


def test_main_fails_when_gap_is_found_and_passes_when_closed(tmp_path, capsys):
    # Arrange
    untraced = make_project(tmp_path / "red", "def test_a():\n    pass\n")
    traced = make_project(
        tmp_path / "green",
        """
        import pytest

        @pytest.mark.req("US-01", "SEC-001")
        def test_a():
            pass
        """,
    )

    # Act / Assert
    assert main(untraced) == 1
    assert "**ДІРКА**" in capsys.readouterr().out
    assert main(traced) == 0
