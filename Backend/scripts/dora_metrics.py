"""
Автоматичний підрахунок DORA-метрик (Лаб 10, бонус «Автоматичний підрахунок метрик»).

Бере історію запусків workflow «CI Pipeline» на гілці main з GitHub Actions (через GitHub CLI `gh`)
і за визначеннями з docs/ci-cd/dora-summary.md обчислює:

- частоту розгортань: розгортання = завершений запуск CI Pipeline на main після злиття PR;
- час виконання змін: від першого коміту PR (authoredDate) до завершення запуску на main,
  окремо з часткою черги (createdAt -> перший startedAt) і виконання (перший startedAt -> останній completedAt);
- частку невдалих змін: червоні запуски / усі запуски на main;
- час відновлення: від завершення червоного запуску до завершення наступного зеленого.

Запуск з кореня репозиторію (потрібен `gh auth login`):
    python Backend/scripts/dora_metrics.py --since 2026-10-20 --until 2026-11-13
Без мережі - з уже збережених доказів docs/ci-cd/evidence/:
    python Backend/scripts/dora_metrics.py --offline
Результат завжди пишеться в docs/ci-cd/dora-auto.md. Шляхи зафіксовано в коді й не приймаються
з командного рядка (SonarCloud: path injection), а з `gh` передаються лише перевірені дати.

Примітка щодо використання ШІ: скрипт згенеровано ШІ (Claude) за визначеннями dora-summary.md;
обчислення перевіряють тести scripts/tests/test_dora_metrics.py, результат звірено з ручним підрахунком.
"""

import argparse
import json
import shutil
import statistics
import subprocess  # nosec B404 - викликається лише GitHub CLI з фіксованими аргументами, без shell
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

REPO = "ukma-fin-ssdm-2026/unispace"
WORKFLOW = "CI Pipeline"
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
EVIDENCE_FILE = ROOT_DIR / "docs" / "ci-cd" / "evidence" / "ci-runs-main-2026-10-20_2026-11-13.json"
OUTPUT_FILE = ROOT_DIR / "docs" / "ci-cd" / "dora-auto.md"


@dataclass(frozen=True)
class Run:
    run_id: int
    sha: str
    pr: int
    ok: bool
    created: datetime
    started: datetime
    completed: datetime
    first_commit: datetime

    @property
    def queue_minutes(self):
        return (self.started - self.created).total_seconds() / 60

    @property
    def execution_minutes(self):
        return (self.completed - self.started).total_seconds() / 60

    @property
    def lead_minutes(self):
        return (self.completed - self.first_commit).total_seconds() / 60


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def run_from_record(record):
    """Перетворює запис у форматі доказів (gh run list + jobs + pr) на Run."""
    jobs = [job for job in record["jobs"] if job.get("startedAt") and job.get("completedAt")]
    return Run(
        run_id=record["databaseId"],
        sha=record["headSha"],
        pr=record["pr"]["number"],
        ok=record["conclusion"] == "success",
        created=parse_time(record["createdAt"]),
        started=min(parse_time(job["startedAt"]) for job in jobs),
        completed=max(parse_time(job["completedAt"]) for job in jobs),
        first_commit=parse_time(record["pr"]["firstCommitAuthoredDate"]),
    )


# --- Метрики (чисті функції, перевіряються тестами без мережі) ---


def observation_days(runs):
    """Період спостереження - від першого до останнього створеного запуску, як у ручному підрахунку."""
    created = sorted(run.created for run in runs)
    return (created[-1] - created[0]).total_seconds() / 86400


def deployment_frequency(runs):
    return len(runs) / observation_days(runs)


def change_failure_rate(runs):
    return sum(not run.ok for run in runs) / len(runs)


def restore_minutes(runs):
    """Для кожного червоного запуску - хвилини до завершення наступного зеленого (якщо він уже був)."""
    ordered = sorted(runs, key=lambda run: run.created)
    result = []
    for index, run in enumerate(ordered):
        if run.ok:
            continue
        fixed = next((later for later in ordered[index + 1 :] if later.ok), None)
        if fixed is not None:
            result.append((fixed.completed - run.completed).total_seconds() / 60)
    return result


def lead_time_breakdown(runs):
    """Медіани часу виконання змін, черги й виконання та їхні частки в сумарному часі виконання змін."""
    total_lead = sum(run.lead_minutes for run in runs)
    return {
        "lead_median_hours": statistics.median(run.lead_minutes for run in runs) / 60,
        "queue_median_minutes": statistics.median(run.queue_minutes for run in runs),
        "execution_median_minutes": statistics.median(run.execution_minutes for run in runs),
        "queue_share": sum(run.queue_minutes for run in runs) / total_lead,
        "execution_share": sum(run.execution_minutes for run in runs) / total_lead,
    }


def category_frequency(per_day):
    if per_day >= 1:
        return "Elite"
    return "High" if per_day >= 1 / 7 else "Medium" if per_day >= 1 / 30 else "Low"


def category_lead_time(hours):
    if hours < 24:
        return "Elite"
    return "High" if hours < 24 * 7 else "Medium" if hours < 24 * 30 else "Low"


def category_failure_rate(rate):
    return "Elite" if rate <= 0.15 else "High" if rate <= 0.30 else "Medium" if rate <= 0.45 else "Low"


def category_restore(minutes):
    if minutes is None:
        return "—"
    if minutes < 60:
        return "Elite"
    return "High" if minutes < 24 * 60 else "Medium" if minutes < 7 * 24 * 60 else "Low"


def compute(runs):
    restores = restore_minutes(runs)
    breakdown = lead_time_breakdown(runs)
    per_day = deployment_frequency(runs)
    failure = change_failure_rate(runs)
    restore = statistics.median(restores) if restores else None
    return {
        "runs": len(runs),
        "failed": sum(not run.ok for run in runs),
        "days": observation_days(runs),
        "frequency_per_day": per_day,
        "failure_rate": failure,
        "restore_median_minutes": restore,
        **breakdown,
        "categories": {
            "frequency": category_frequency(per_day),
            "lead_time": category_lead_time(breakdown["lead_median_hours"]),
            "failure_rate": category_failure_rate(failure),
            "restore": category_restore(restore),
        },
    }


def _num(value, digits=1):
    return f"{value:.{digits}f}".replace(".", ",")


def render(metrics, source):
    c = metrics["categories"]
    restore = metrics["restore_median_minutes"]
    restore_text = "немає червоних запусків з наступним зеленим" if restore is None else f"{_num(restore, 0)} хв"
    return f"""# DORA-метрики: автоматичний підрахунок

Згенеровано скриптом `Backend/scripts/dora_metrics.py` ({source}). Не редагуйте вручну - перезапустіть скрипт.

Запусків CI Pipeline на `main`: **{metrics['runs']}** (червоних: {metrics['failed']}), період спостереження \
**{_num(metrics['days'], 2)} доби**.

| Метрика | Формула | Результат | Категорія |
|---|---|---|---|
| Частота розгортань | запуски на `main` / діб спостереження | {_num(metrics['frequency_per_day'])} / день | \
{c['frequency']} |
| Час виконання змін | медіана (завершення запуску на `main` − перший коміт PR) | \
{_num(metrics['lead_median_hours'])} год | {c['lead_time']} |
| Частка невдалих змін | червоні запуски / усі запуски на `main` | {_num(metrics['failure_rate'] * 100, 2)}% | \
{c['failure_rate']} |
| Час відновлення | медіана (завершення наступного зеленого − завершення червоного) | {restore_text} | {c['restore']} |

**Черга і виконання в часі виконання змін:**

| Складова | Медіана | Частка в сумарному часі виконання змін |
|---|---|---|
| Черга (`createdAt` → перший `startedAt`) | {_num(metrics['queue_median_minutes'])} хв | \
{_num(metrics['queue_share'] * 100, 2)}% |
| Виконання (перший `startedAt` → останній `completedAt`) | {_num(metrics['execution_median_minutes'])} хв | \
{_num(metrics['execution_share'] * 100, 2)}% |
| Решта (від першого коміту PR до злиття: розробка, огляд, очікування) | — | \
{_num((1 - metrics['queue_share'] - metrics['execution_share']) * 100, 2)}% |
"""


# --- Збір даних через GitHub CLI ---


def _gh(*args):
    executable = shutil.which("gh")
    if executable is None:
        raise SystemExit("Не знайдено GitHub CLI (gh). Встановіть його або запустіть з --offline.")
    # nosec B603: без shell, аргументи - фіксовані рядки, числові id і перевірені дати.
    completed = subprocess.run([executable, *args], capture_output=True, text=True, check=True)  # nosec B603
    return json.loads(completed.stdout)


def fetch_records(since, until):
    records = _gh(
        "run",
        "list",
        "-R",
        REPO,
        "--branch",
        "main",
        "--workflow",
        WORKFLOW,
        "--limit",
        "500",
        "--created",
        f"{since.isoformat()}..{until.isoformat()}",
        "--json",
        "databaseId,headSha,conclusion,attempt,createdAt,event",
    )
    first_commits = {}
    for record in records:
        record["jobs"] = _gh("run", "view", str(record["databaseId"]), "-R", REPO, "--json", "jobs")["jobs"]
        pulls = _gh("api", f"repos/{REPO}/commits/{record['headSha']}/pulls")
        number = pulls[0]["number"]
        if number not in first_commits:
            commits = _gh("pr", "view", str(number), "-R", REPO, "--json", "commits")["commits"]
            first_commits[number] = min(commit["authoredDate"] for commit in commits)
        record["pr"] = {"number": number, "firstCommitAuthoredDate": first_commits[number]}
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description="Автоматичний підрахунок DORA-метрик для CI Pipeline на main")
    parser.add_argument("--since", type=date.fromisoformat, help="перша дата періоду, РРРР-ММ-ДД")
    parser.add_argument("--until", type=date.fromisoformat, help="остання дата періоду, РРРР-ММ-ДД")
    parser.add_argument("--offline", action="store_true", help="рахувати з docs/ci-cd/evidence без мережі")
    args = parser.parse_args(argv)

    if args.offline:
        records = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
        source = f"дані з `docs/ci-cd/evidence/{EVIDENCE_FILE.name}`"
    elif args.since and args.until:
        records = fetch_records(args.since, args.until)
        source = f"GitHub Actions API, період {args.since.isoformat()}..{args.until.isoformat()}"
    else:
        parser.error("вкажіть --since і --until або --offline")

    metrics = compute([run_from_record(record) for record in records])
    OUTPUT_FILE.write_text(render(metrics, source), encoding="utf-8")
    print(f"Збережено {OUTPUT_FILE.relative_to(ROOT_DIR)}: {metrics['runs']} запусків", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
