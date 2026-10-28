"""
Тести скрипта підсумку CI (scripts/ci_summary.py).

Примітка щодо використання ШІ: тести згенеровано ШІ (Claude), переглянуто автором PR.
"""

import json
import textwrap

from scripts.ci_summary import read_coverage, read_test_results, render

JUNIT_PASSED = """
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="0" skipped="1" tests="3" time="2.5">
    <testcase classname="api.tests.test_a" name="test_one" time="0.1"/>
    <testcase classname="api.tests.test_a" name="test_two" time="0.1"/>
    <testcase classname="api.tests.test_a" name="test_three" time="0.1"><skipped message="skip"/></testcase>
  </testsuite>
</testsuites>
"""

JUNIT_FAILED = """
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="1" failures="1" skipped="0" tests="3" time="1.0">
    <testcase classname="api.tests.test_a" name="test_ok" time="0.1"/>
    <testcase classname="api.tests.test_a" name="test_broken" time="0.1"><failure message="assert"/></testcase>
    <testcase classname="api.tests.test_b" name="test_crash" time="0.1"><error message="boom"/></testcase>
  </testsuite>
</testsuites>
"""


def file_summary(percent, statements, covered, branches, covered_branches):
    return {
        "summary": {
            "percent_covered": percent,
            "num_statements": statements,
            "covered_lines": covered,
            "missing_lines": statements - covered,
            "num_branches": branches,
            "covered_branches": covered_branches,
        }
    }


def write_coverage(path, total_percent=90.0):
    data = {
        "totals": file_summary(total_percent, 100, 92, 20, 15)["summary"],
        "files": {
            "api/views.py": file_summary(95.0, 60, 58, 10, 9),
            "api/models.py": file_summary(70.0, 40, 28, 10, 6),
        },
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def write_junit(path, text):
    path.write_text(textwrap.dedent(text).strip(), encoding="utf-8")
    return path


def test_passed_run_counts_tests_and_skips(tmp_path):
    # Act
    results = read_test_results(write_junit(tmp_path / "results.xml", JUNIT_PASSED))

    # Assert
    assert results["tests"] == 3
    assert results["passed"] == 2
    assert results["skipped"] == 1
    assert results["failed_tests"] == []


def test_failed_and_errored_tests_are_listed(tmp_path):
    # Act
    results = read_test_results(write_junit(tmp_path / "results.xml", JUNIT_FAILED))

    # Assert
    assert results["passed"] == 1
    assert results["failed_tests"] == ["api.tests.test_a::test_broken", "api.tests.test_b::test_crash"]


def test_coverage_files_are_sorted_from_lowest(tmp_path):
    # Act
    coverage = read_coverage(write_coverage(tmp_path / "coverage.json"))

    # Assert
    assert [item["name"] for item in coverage["files"]] == ["api/models.py", "api/views.py"]
    assert coverage["total"]["percent"] == 90.0


def test_missing_files_are_reported_instead_of_crashing(tmp_path):
    # Act
    text = render(read_test_results(tmp_path / "nope.xml"), read_coverage(tmp_path / "nope.json"))

    # Assert
    assert "Результатів тестів немає" in text
    assert "Звіту покриття немає" in text


def test_summary_shows_green_gate_and_file_table(tmp_path):
    # Arrange
    tests = read_test_results(write_junit(tmp_path / "results.xml", JUNIT_PASSED))
    coverage = read_coverage(write_coverage(tmp_path / "coverage.json", total_percent=90.0))

    # Act
    text = render(tests, coverage, threshold=75)

    # Assert
    assert "✅ **Тести:** 2 пройшло, 0 впало" in text
    assert "✅ **Покриття:** 90.0% (поріг 75%): рядки 92.0%, гілки 75.0%" in text
    assert "| `api/models.py` | 70.0% | 28/40 | 12 | 6/10 |" in text


def test_summary_shows_red_marks_for_failures_and_low_coverage(tmp_path):
    # Arrange
    tests = read_test_results(write_junit(tmp_path / "results.xml", JUNIT_FAILED))
    coverage = read_coverage(write_coverage(tmp_path / "coverage.json", total_percent=60.0))

    # Act
    text = render(tests, coverage, threshold=75)

    # Assert
    assert "❌ **Тести:**" in text
    assert "- `api.tests.test_a::test_broken`" in text
    assert "❌ **Покриття:** 60.0%" in text
