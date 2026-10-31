"""
Парсер розкладу САЗ НаУКМА (FR-004): адаптер, ізольований від бази даних (A-001, R-001).

САЗ не має публічного API і показує розклад лише після входу, тому UniSpace не завантажує сторінку сам,
а розбирає збережену диспетчером HTML-сторінку попереднього перегляду розкладу
(my.ukma.edu.ua/schedule/preview/...). Це таблиця, згенерована з xlsx-файлу:
колонки «День | Час | Дисципліна, викладач | Група | Тижні | Аудиторія», дні й час об'єднано через rowspan.

Парсер використовує лише стандартну бібліотеку (html.parser), щоб не додавати залежностей.
Якщо розмітка зміниться так, що таблицю розкладу не знайдено, кидається SazParseError:
імпорт тоді не змінює вже імпортовані дані (REL-002).

Примітка щодо використання ШІ: модуль згенеровано ШІ (Claude) за збереженою сторінкою САЗ;
поведінку перевіряють тести test_saz_parser.py на анонімізованій фікстурі.
"""

import re
from dataclasses import dataclass, field
from datetime import time
from html.parser import HTMLParser

DAYS = {"понеділок": 0, "вівторок": 1, "середа": 2, "четвер": 3, "пятниця": 4, "субота": 5, "неділя": 6}
HEADER = ["день", "час", "дисципліна, викладач", "група", "тижні", "аудиторія"]
LECTURE = "лекція"

# Текст клітинок уже нормалізовано (пробіли зведено до одного), тож у шаблонах достатньо « ?» замість «\s*»;
# квантифікатори обмежено, щоб уникнути надлінійного перебору (SonarCloud python:S5852).
_TIME_RANGE = re.compile(r"(\d{1,2})[:.](\d{2}) ?[-–] ?(\d{1,2})[:.](\d{2})")
_ROOM = re.compile(r"(\d{1,3}) ?- ?(\d{1,4})")
_TEACHER = re.compile(r"[А-ЯІЇЄҐ]\. ?(?:[А-ЯІЇЄҐ]\. ?)?[А-ЯІЇЄҐ][а-яіїєґ'’ʼ`-]{1,40}$")
_SPECIALTY = re.compile(r"Спеціальність ?[\"«“]([^\"»”]{1,150})[\"»”] ?, ?(\d{1,2}) ?р\.? ?н", re.IGNORECASE)
_ONLINE_ONLY = {"дистанційно", "онлайн"}


class SazParseError(ValueError):
    """Сторінка не схожа на розклад САЗ: таблицю або заголовок не знайдено."""


@dataclass(frozen=True)
class ScheduleEntry:
    """Один рядок розкладу: заняття, що повторюється в зазначені тижні."""

    weekday: int  # 0 - понеділок
    start: time
    end: time
    subject: str
    teacher: str  # «В.С. Проценко»; порожньо, якщо викладача не вказано
    group: str  # «лекція» або номер практичної групи
    weeks: tuple
    room_raw: str
    room: tuple | None  # (корпус, номер у корпусі), напр. ("1", "223"); None - дистанційно або не розпізнано
    online_only: bool


@dataclass
class ParsedSchedule:
    specialty: str
    year: int
    entries: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class _TableCollector(HTMLParser):
    """Збирає таблиці як списки рядків клітинок (текст, rowspan, colspan)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self._row, self._cell, self._depth = [], None, None, 0
        self.texts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self._depth += 1
            self.tables.append([])
        elif tag == "tr" and self._depth:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            span = (int(attrs.get("rowspan") or 1), int(attrs.get("colspan") or 1))
            self._cell = [[], span]
        elif tag == "br" and self._cell is not None:
            self._cell[0].append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            text = re.sub(r"\s+", " ", "".join(self._cell[0]).replace("\xa0", " ")).strip()
            self._row.append((text, *self._cell[1]))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.tables[-1].append(self._row)
            self._row = None
        elif tag == "table" and self._depth:
            self._depth -= 1

    def handle_data(self, data):
        if self._cell is not None:
            self._cell[0].append(data)
        else:
            self.texts.append(data)


def _expand_spans(rows):
    """Розгортає rowspan/colspan у прямокутну сітку тексту."""
    grid, pending = [], {}
    for row in rows:
        out, col, cells = [], 0, iter(row)
        cell = next(cells, None)
        while cell is not None or col in pending:
            if col in pending:
                left, text = pending[col]
                out.append(text)
                if left > 1:
                    pending[col] = (left - 1, text)
                else:
                    del pending[col]
                col += 1
                continue
            text, rowspan, colspan = cell
            for offset in range(colspan):
                value = text if offset == 0 else ""
                out.append(value)
                if rowspan > 1:
                    pending[col] = (rowspan - 1, value)
                col += 1
            cell = next(cells, None)
        grid.append(out)
    return grid


def _normalize(text):
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _day_index(text):
    key = re.sub(r"['’ʼ`]", "", text).strip().lower()
    return DAYS.get(key)


def parse_weeks(text):
    """«2-12» -> (2, ..., 12); «1,3,5-7» -> (1, 3, 5, 6, 7). Нерозпізнане -> ValueError."""
    weeks = set()
    for part in re.split(r"[,;]", text):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", part)
        if match:
            first, last = int(match.group(1)), int(match.group(2))
            if first > last:
                raise ValueError(f"Некоректний діапазон тижнів: {text}")
            weeks.update(range(first, last + 1))
        elif part.isdigit():
            weeks.add(int(part))
        else:
            raise ValueError(f"Не вдалося розпізнати тижні: {text}")
    if not weeks:
        raise ValueError("Тижні не вказано")
    return tuple(sorted(weeks))


def parse_room(text):
    """«1-225 /онлайн» -> (('1', '225'), False); «Дистанційно» -> (None, True); «10к» -> (None, False)."""
    normalized = _normalize(text).lower()
    match = _ROOM.search(normalized)
    if match:
        return (match.group(1), match.group(2)), False
    return None, normalized in _ONLINE_ONLY


def split_subject_and_teacher(text):
    """«Функціональне програмування, доц. В.С. Проценко» -> («Функціональне програмування», «В.С. Проценко»)."""
    subject, _, rest = _normalize(text).rpartition(",")
    if not subject:
        return _normalize(text), ""
    match = _TEACHER.search(rest.strip())
    if not match:
        return subject.strip(), ""
    teacher = re.sub(r"\. ?", ". ", match.group(0)).strip()
    teacher = re.sub(r"\. (?=[А-ЯІЇЄҐ]\.)", ".", teacher)  # «В. С. Проценко» -> «В.С. Проценко»
    return subject.strip(), teacher


def _parse_time(text):
    match = _TIME_RANGE.search(text)
    if not match:
        return None
    h1, m1, h2, m2 = (int(value) for value in match.groups())
    return time(h1, m1), time(h2, m2)


def parse_schedule(html):
    """Повертає ParsedSchedule зі сторінки попереднього перегляду розкладу САЗ."""
    collector = _TableCollector()
    collector.feed(html)

    for table in collector.tables:
        grid = _expand_spans(table)
        header_index = next(
            (i for i, row in enumerate(grid) if [c.lower() for c in row[:6]] == HEADER),
            None,
        )
        if header_index is not None:
            break
    else:
        raise SazParseError("Таблицю розкладу САЗ не знайдено: заголовок «День | Час | Дисципліна, викладач ...»")

    page_text = " ".join(_normalize(cell) for row in grid[:header_index] for cell in row if cell)
    match = _SPECIALTY.search(page_text)
    if not match:
        raise SazParseError("Не знайдено спеціальність і рік навчання в заголовку розкладу")
    schedule = ParsedSchedule(specialty=_normalize(match.group(1)), year=int(match.group(2)))

    for number, row in enumerate(grid[header_index + 1 :], start=header_index + 2):
        day, slot, subject_cell, group, weeks_cell, room_cell = (row + [""] * 6)[:6]
        if not subject_cell:
            continue  # порожній слот
        weekday, times = _day_index(day), _parse_time(slot)
        if weekday is None or times is None:
            schedule.warnings.append(f"Рядок {number}: не розпізнано день або час ({day!r}, {slot!r})")
            continue
        try:
            weeks = parse_weeks(weeks_cell)
        except ValueError as error:
            schedule.warnings.append(f"Рядок {number}: {error}")
            continue
        subject, teacher = split_subject_and_teacher(subject_cell)
        room, online_only = parse_room(room_cell)
        schedule.entries.append(
            ScheduleEntry(
                weekday=weekday,
                start=times[0],
                end=times[1],
                subject=subject,
                teacher=teacher,
                group=_normalize(group).lower() or LECTURE,
                weeks=weeks,
                room_raw=_normalize(room_cell),
                room=room,
                online_only=online_only,
            )
        )
    return schedule
