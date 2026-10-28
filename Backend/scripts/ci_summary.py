"""
Підсумок прогону CI для сторінки GitHub Actions ($GITHUB_STEP_SUMMARY): кількість тестів,
загальне покриття з порогом і таблиця покриття по файлах.

Скрипт читає файли, які щойно створив pytest у цьому ж job:
  test-results.xml  (--junitxml)   і   coverage.json  (--cov-report=json)
і друкує Markdown у stdout; у CI вивід дописується до $GITHUB_STEP_SUMMARY.
Шляхи зафіксовано в коді. Скрипт ніколи не валить збірку: це звіт, а не перевірка.

Запуск з папки Backend:  python scripts/ci_summary.py

Примітка щодо використання ШІ: скрипт згенеровано ШІ (Claude) для відпрацювання Lab07;
поведінку перевіряють тести scripts/tests/test_ci_summary.py.
"""

import json
import os
import sys

# Файл результатів створює pytest у цьому ж job, тому він довірений; ElementTree не завантажує зовнішні сутності.
import xml.etree.ElementTree as ElementTree  # nosec B405
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_RESULTS = BACKEND_DIR / "test-results.xml"
COVERAGE_JSON = BACKEND_DIR / "coverage.json"
DEFAULT_THRESHOLD = 75  # той самий поріг, що --cov-fail-under у ci.yml
MAX_FAILURES_SHOWN = 20


def read_test_results(path):
    """Повертає підсумок JUnit-звіту pytest або None, якщо файлу немає."""
    path = Path(path)
    if not path.exists():
        return None
    root = ElementTree.parse(path).getroot()  # nosec B314
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")

    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}
    failed = []
    for suite in suites:
        for key in ("tests", "failures", "errors", "skipped"):
            totals[key] += int(suite.get(key, 0))
        totals["time"] += float(suite.get("time", 0))
        for case in suite.iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                failed.append(f"{case.get('classname')}::{case.get('name')}")
    totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    totals["failed_tests"] = failed
    return totals


def read_coverage(path):
    """Повертає {"total": {...}, "files": [{...}]} з coverage.json або None, якщо файлу немає."""
    path = Path(path)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    files = [{"name": name, **_summary(details["summary"])} for name, details in data.get("files", {}).items()]
    files.sort(key=lambda item: (item["percent"], item["name"]))
    return {"total": _summary(data["totals"]), "files": files}


def _summary(summary):
    return {
        "percent": float(summary.get("percent_covered", 0.0)),
        "statements": summary.get("num_statements", 0),
        "covered_lines": summary.get("covered_lines", 0),
        "missing_lines": summary.get("missing_lines", 0),
        "branches": summary.get("num_branches", 0),
        "covered_branches": summary.get("covered_branches", 0),
    }


def _ratio(part, whole):
    return f"{100 * part / whole:.1f}%" if whole else "—"


def render(tests, coverage, threshold=DEFAULT_THRESHOLD):
    lines = ["## Підсумок тестів і покриття", ""]

    if tests is None:
        lines += ["⚠️ Результатів тестів немає: pytest не дійшов до кінця або не створив test-results.xml.", ""]
    else:
        status = "✅" if tests["failures"] == 0 and tests["errors"] == 0 else "❌"
        lines += [
            f"{status} **Тести:** {tests['passed']} пройшло, {tests['failures']} впало, "
            f"{tests['errors']} з помилкою, {tests['skipped']} пропущено "
            f"(усього {tests['tests']}, {tests['time']:.1f} с)",
            "",
        ]
        if tests["failed_tests"]:
            lines.append("**Тести, що впали:**")
            lines += [f"- `{name}`" for name in tests["failed_tests"][:MAX_FAILURES_SHOWN]]
            hidden = len(tests["failed_tests"]) - MAX_FAILURES_SHOWN
            if hidden > 0:
                lines.append(f"- … і ще {hidden}")
            lines.append("")

    if coverage is None:
        lines += ["⚠️ Звіту покриття немає: coverage.json не створено.", ""]
        return "\n".join(lines)

    total = coverage["total"]
    gate = "✅" if total["percent"] >= threshold else "❌"
    lines += [
        f"{gate} **Покриття:** {total['percent']:.1f}% (поріг {threshold}%): "
        f"рядки {_ratio(total['covered_lines'], total['statements'])}, "
        f"гілки {_ratio(total['covered_branches'], total['branches'])}",
        "",
        "<details><summary>Покриття по файлах (від найменшого)</summary>",
        "",
        "| Файл | Покриття | Рядки | Непокриті рядки | Гілки |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in coverage["files"]:
        lines.append(
            f"| `{item['name']}` | {item['percent']:.1f}% | {item['covered_lines']}/{item['statements']} "
            f"| {item['missing_lines']} | {item['covered_branches']}/{item['branches']} |"
        )
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def threshold_from_env():
    try:
        return int(os.environ.get("COVERAGE_THRESHOLD", DEFAULT_THRESHOLD))
    except ValueError:
        return DEFAULT_THRESHOLD


def main():
    print(render(read_test_results(TEST_RESULTS), read_coverage(COVERAGE_JSON), threshold_from_env()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
