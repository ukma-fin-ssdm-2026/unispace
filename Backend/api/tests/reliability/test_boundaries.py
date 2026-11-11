"""
Тест надійності: граничні значення вводу (Лаб 9, REL-H04).

Атрибути rowspan/colspan зі збереженої сторінки САЗ перевіряються на межах дозволеного діапазону:
1 і MAX_ROWSPAN (200) / MAX_COLSPAN (20) приймаються, а 0 і MAX + 1 відхиляються з SazParseError.
Так перевіряється, що межа стоїть рівно там, де задумано: без «помилки на одиницю» в обидва боки.

Запуск: cd Backend && python -m pytest api/tests/reliability -v

Примітка щодо використання ШІ: тест написано з допомогою ШІ (Claude) за scavenger-hunt.md (REL-H04);
запуск `pytest` локально і в CI виконує авторка PR (Ольга Михайлик).
"""

from pathlib import Path

import pytest

from api.services.saz_parser import MAX_COLSPAN, MAX_ROWSPAN, SazParseError, parse_schedule

pytestmark = pytest.mark.req("REL-002")

HTML = (Path(__file__).parent.parent / "fixtures" / "saz" / "schedule_preview.html").read_text(encoding="utf-8")
ORIGINAL = {"rowspan": 'rowspan="2"', "colspan": 'colspan="4"'}  # перші атрибути у фікстурі
LIMITS = {"rowspan": MAX_ROWSPAN, "colspan": MAX_COLSPAN}


def page_with(attribute, value):
    html = HTML.replace(ORIGINAL[attribute], f'{attribute}="{value}"', 1)
    assert html != HTML
    return html


@pytest.mark.parametrize("attribute", ["rowspan", "colspan"])
@pytest.mark.parametrize("value", [lambda limit: 1, lambda limit: limit], ids=["min=1", "max"])
def test_values_on_the_boundary_are_accepted(attribute, value):
    # Act / Assert: сторінка розбирається без винятку
    schedule = parse_schedule(page_with(attribute, value(LIMITS[attribute])))
    assert schedule.specialty


@pytest.mark.parametrize("attribute", ["rowspan", "colspan"])
@pytest.mark.parametrize("value", [lambda limit: 0, lambda limit: limit + 1], ids=["min-1=0", "max+1"])
def test_values_just_outside_the_boundary_are_rejected(attribute, value):
    # Act / Assert: на один крок за межею - чітка помилка розбору
    with pytest.raises(SazParseError, match=f"Некоректний атрибут {attribute}"):
        parse_schedule(page_with(attribute, value(LIMITS[attribute])))
