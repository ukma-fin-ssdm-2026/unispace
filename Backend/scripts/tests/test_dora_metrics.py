"""
Тести автоматичного підрахунку DORA-метрик (scripts/dora_metrics.py) на синтетичних запусках, без мережі.

Примітка щодо використання ШІ: тести згенеровано ШІ (Claude), переглянуто авторкою PR (Ольга Михайлик).
"""

from datetime import datetime, timedelta, timezone

import pytest

from scripts.dora_metrics import (
    Run,
    category_failure_rate,
    category_frequency,
    category_lead_time,
    category_restore,
    change_failure_rate,
    compute,
    deployment_frequency,
    lead_time_breakdown,
    render,
    restore_minutes,
    run_from_record,
)

T0 = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)


def make_run(run_id, created_min, *, ok=True, queue=1, execution=2, first_commit_min=-60):
    created = T0 + timedelta(minutes=created_min)
    started = created + timedelta(minutes=queue)
    return Run(
        run_id=run_id,
        sha=f"{run_id:07d}",
        pr=run_id,
        ok=ok,
        created=created,
        started=started,
        completed=started + timedelta(minutes=execution),
        first_commit=created + timedelta(minutes=first_commit_min),
    )


def test_run_from_record_uses_earliest_start_and_latest_completion():
    record = {
        "databaseId": 1,
        "headSha": "abc",
        "conclusion": "success",
        "createdAt": "2026-11-01T10:00:00Z",
        "jobs": [
            {"startedAt": "2026-11-01T10:02:00Z", "completedAt": "2026-11-01T10:05:00Z"},
            {"startedAt": "2026-11-01T10:01:00Z", "completedAt": "2026-11-01T10:09:00Z"},
        ],
        "pr": {"number": 7, "firstCommitAuthoredDate": "2026-11-01T09:00:00Z"},
    }

    run = run_from_record(record)

    assert run.queue_minutes == 1
    assert run.execution_minutes == 8
    assert run.lead_minutes == 69


def test_frequency_and_failure_rate_over_observation_period():
    runs = [make_run(1, 0), make_run(2, 12 * 60, ok=False), make_run(3, 24 * 60), make_run(4, 48 * 60)]

    assert deployment_frequency(runs) == pytest.approx(2.0)  # 4 запуски за 2 доби
    assert change_failure_rate(runs) == pytest.approx(0.25)


def test_restore_time_is_measured_to_next_green_run_only():
    runs = [
        make_run(1, 0, ok=False),  # завершено о 0+1+2 = 3 хв
        make_run(2, 10, ok=False),  # другий червоний поспіль
        make_run(3, 40),  # перший зелений: завершено о 43 хв
        make_run(4, 100, ok=False),  # червоний без наступного зеленого не враховується
    ]

    assert restore_minutes(runs) == [40, 30]


def test_queue_and_execution_shares_of_lead_time():
    runs = [make_run(1, 0, queue=2, execution=8, first_commit_min=-90)]  # lead = 90 + 10 = 100 хв

    breakdown = lead_time_breakdown(runs)

    assert breakdown["queue_share"] == pytest.approx(0.02)
    assert breakdown["execution_share"] == pytest.approx(0.08)
    assert breakdown["lead_median_hours"] == pytest.approx(100 / 60)


@pytest.mark.parametrize(
    "function,value,expected",
    [
        (category_frequency, 1.0, "Elite"),
        (category_frequency, 0.5, "High"),
        (category_lead_time, 23.9, "Elite"),
        (category_lead_time, 24.0, "High"),
        (category_failure_rate, 0.15, "Elite"),
        (category_failure_rate, 0.16, "High"),
        (category_restore, 59, "Elite"),
        (category_restore, None, "—"),
    ],
)
def test_category_boundaries(function, value, expected):
    assert function(value) == expected


def test_render_contains_all_four_metrics_and_shares():
    runs = [make_run(1, 0), make_run(2, 60, ok=False), make_run(3, 24 * 60)]

    report = render(compute(runs), "тестові дані")

    for name in ("Частота розгортань", "Час виконання змін", "Частка невдалих змін", "Час відновлення", "Черга"):
        assert name in report
