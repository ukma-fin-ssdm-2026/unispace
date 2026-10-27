"""
Автоматична перевірка простежуваності (Lab07, бонус): зіставляє ID вимог із docs/requirements/rtm.md
з мітками @pytest.mark.req("...") у тестах Backend/api/tests і завершується з кодом 1, якщо:

1. вимога з RTM не має жодного тесту і не внесена до винятків;
2. тест не посилається на жодну вимогу і не внесений до винятків;
3. мітка посилається на ID, якого немає в RTM (друкарська помилка);
4. виняток застарів: вимога вже має тест або тест уже має мітку.

Мітки читаються статично (через ast), тож скрипт не потребує Django і бази даних.
Мітка може стояти на функції, класі (для unittest-класів) або в pytestmark модуля чи класу.

Запуск з папки Backend:  python scripts/check_traceability.py
Шляхи до файлів зафіксовано в коді і не приймаються з командного рядка, щоб скрипт не можна було
змусити прочитати довільний файл (SonarCloud: path injection).

Примітка щодо використання ШІ: скрипт згенеровано ШІ (Claude) за вимогами бонусу Lab07;
поведінку перевіряють тести scripts/tests/test_check_traceability.py.
"""

import ast
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RTM = BACKEND_DIR.parent / "docs" / "requirements" / "rtm.md"
DEFAULT_TESTS = BACKEND_DIR / "api" / "tests"
DEFAULT_EXCEPTIONS = BACKEND_DIR / "traceability.toml"

RTM_ROW_ID = re.compile(r"^\|\s*\*\*([A-Z]+-\d+)\*\*\s*\|")


@dataclass
class Report:
    requirements: list[str]
    tests: dict[str, set[str]]
    errors: list[str] = field(default_factory=list)

    def tests_for(self, requirement):
        return sorted(test for test, ids in self.tests.items() if requirement in ids)


def read_requirement_ids(rtm_path):
    """ID вимог - перший стовпець рядків RTM, позначений жирним: | **US-01** | ..."""
    ids = []
    for line in Path(rtm_path).read_text(encoding="utf-8").splitlines():
        match = RTM_ROW_ID.match(line.strip())
        if match:
            ids.append(match.group(1))
    return ids


def _req_ids_from_call(node):
    """ID з виклику pytest.mark.req("US-01", "SEC-001"); для інших виразів - порожня множина."""
    if not isinstance(node, ast.Call):
        return set()
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "req"):
        return set()
    owner = func.value
    if not (isinstance(owner, ast.Attribute) and owner.attr == "mark"):
        return set()
    return {arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}


def _req_ids_from_expression(node):
    """Мітки з декоратора або значення pytestmark (окрема мітка чи список/кортеж міток)."""
    if isinstance(node, (ast.List, ast.Tuple)):
        ids = set()
        for element in node.elts:
            ids |= _req_ids_from_call(element)
        return ids
    return _req_ids_from_call(node)


def _pytestmark_ids(body):
    ids = set()
    for statement in body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in statement.targets
        ):
            ids |= _req_ids_from_expression(statement.value)
    return ids


def _decorator_ids(node):
    ids = set()
    for decorator in node.decorator_list:
        ids |= _req_ids_from_expression(decorator)
    return ids


def _is_test_function(node):
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")


def collect_test_marks(tests_dir, base_dir=None):
    """
    Повертає {"api/tests/test_x.py::Class::test_y": {"US-01", ...}} для всіх тестів у теці.
    Шляхи рахуються від base_dir; за замовчуванням - тека на два рівні вище (Backend для api/tests).
    """
    tests_dir = Path(tests_dir).resolve()
    base_dir = Path(base_dir).resolve() if base_dir else tests_dir.parent.parent
    tests = {}
    for path in sorted(tests_dir.glob("test_*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"))
        relative = path.relative_to(base_dir).as_posix()
        module_ids = _pytestmark_ids(module.body)

        for node in module.body:
            if _is_test_function(node):
                tests[f"{relative}::{node.name}"] = module_ids | _decorator_ids(node)
            elif isinstance(node, ast.ClassDef):
                class_ids = module_ids | _decorator_ids(node) | _pytestmark_ids(node.body)
                for item in node.body:
                    if _is_test_function(item):
                        tests[f"{relative}::{node.name}::{item.name}"] = class_ids | _decorator_ids(item)
    return tests


def read_exceptions(path):
    if not Path(path).exists():
        return {}, {}
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("requirements_without_tests", {}), data.get("tests_without_requirements", {})


def _matches(test_id, prefix):
    """Виняток для тесту задається повним ID або префіксом файлу/класу: api/tests/test_x.py::Class."""
    return test_id == prefix or test_id.startswith(prefix + "::")


def check(requirements, tests, requirement_exceptions, test_exceptions):
    report = Report(requirements=requirements, tests=tests)
    known = set(requirements)

    for test_id, ids in sorted(tests.items()):
        for unknown in sorted(ids - known):
            report.errors.append(f"Тест {test_id} посилається на {unknown}, якого немає в rtm.md")

    for requirement in requirements:
        covered = bool(report.tests_for(requirement))
        if not covered and requirement not in requirement_exceptions:
            report.errors.append(f"Вимога {requirement} не має жодного тесту")
        if covered and requirement in requirement_exceptions:
            report.errors.append(f"Виняток для {requirement} застарів: вимога вже має тести, приберіть її з винятків")

    for requirement in sorted(set(requirement_exceptions) - known):
        report.errors.append(f"Виняток для {requirement}: такої вимоги немає в rtm.md")

    for test_id, ids in sorted(tests.items()):
        exempt = any(_matches(test_id, prefix) for prefix in test_exceptions)
        if not ids and not exempt:
            report.errors.append(f"Тест {test_id} не посилається на жодну вимогу")

    for prefix in sorted(test_exceptions):
        matched = [test_id for test_id in tests if _matches(test_id, prefix)]
        if not matched:
            report.errors.append(f"Виняток для тестів {prefix} ні до чого не відноситься, приберіть його")
        elif all(tests[test_id] for test_id in matched):
            report.errors.append(f"Виняток для тестів {prefix} застарів: тести вже мають мітки вимог")

    return report


def format_summary(report, requirement_exceptions):
    lines = ["| Вимога | Тестів | Статус |", "|---|---|---|"]
    for requirement in report.requirements:
        count = len(report.tests_for(requirement))
        if count:
            state = "покрито"
        elif requirement in requirement_exceptions:
            state = f"виняток: {requirement_exceptions[requirement]}"
        else:
            state = "**ДІРКА**"
        lines.append(f"| {requirement} | {count} | {state} |")
    linked = sum(1 for ids in report.tests.values() if ids)
    lines.append("")
    lines.append(f"Тестів з мітками вимог: {linked} з {len(report.tests)}.")
    return "\n".join(lines)


def run(rtm_path, tests_dir, exceptions_path):
    """Перевіряє простежуваність для заданих файлів; повертає код виходу (0 - гаразд, 1 - є дірки)."""
    requirements = read_requirement_ids(rtm_path)
    tests = collect_test_marks(tests_dir)
    requirement_exceptions, test_exceptions = read_exceptions(exceptions_path)
    report = check(requirements, tests, requirement_exceptions, test_exceptions)

    print(format_summary(report, requirement_exceptions))
    if report.errors:
        print(f"\nЗнайдено проблем простежуваності: {len(report.errors)}")
        for error in report.errors:
            print(f"  - {error}")
        return 1
    print("\nПростежуваність у порядку: кожна вимога має тест або обґрунтований виняток, кожен тест - вимогу.")
    return 0


def main():
    return run(DEFAULT_RTM, DEFAULT_TESTS, DEFAULT_EXCEPTIONS)


if __name__ == "__main__":
    sys.exit(main())
