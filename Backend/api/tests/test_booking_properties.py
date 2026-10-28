from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from api.booking_rules import BookingRuleError, booking_duration, validate_attendees_fit_room

ZONES = [ZoneInfo(name) for name in ("UTC", "Europe/Kyiv", "America/New_York", "Asia/Tokyo", "Australia/Lord_Howe")]

# Діапазон 2020-2035 включає високосні роки (2024, 2028, 2032) і дати переходу годинників.
aware_datetimes = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2035, 12, 31),
    timezones=st.sampled_from(ZONES),
)
positive_gaps = st.timedeltas(min_value=timedelta(seconds=1), max_value=timedelta(days=2))


@pytest.mark.req("US-03")
@settings(max_examples=300)
@given(start=aware_datetimes, gap=positive_gaps, end_zone=st.sampled_from(ZONES))
def test_duration_is_always_positive_and_equals_real_elapsed_time(start, gap, end_zone):
    """Для будь-якої пари часу, де кінець пізніше за початок, тривалість додатна і дорівнює реальному проміжку."""
    end = (start.astimezone(timezone.utc) + gap).astimezone(end_zone)

    duration = booking_duration(start, end)

    assert duration > timedelta(0)
    assert duration == gap


@pytest.mark.req("US-03")
@settings(max_examples=200)
@given(start=aware_datetimes, gap=positive_gaps)
def test_reversed_interval_is_always_rejected(start, gap):
    """Якщо кінець не пізніше за початок, завжди помилка."""
    end = start.astimezone(timezone.utc) + gap
    with pytest.raises(BookingRuleError):
        booking_duration(end, start)


@pytest.mark.req("US-03")
@settings(max_examples=200)
@given(start=aware_datetimes, gap=positive_gaps)
def test_duration_is_additive(start, gap):
    """Тривалість [start, end] дорівнює сумі тривалостей [start, middle] і [middle, end]."""
    middle = start.astimezone(timezone.utc) + gap
    end = middle + gap
    assert booking_duration(start, end) == booking_duration(start, middle) + booking_duration(middle, end)


@pytest.mark.req("US-10")
@given(capacity=st.integers(min_value=1, max_value=10_000), data=st.data())
def test_attendees_up_to_capacity_always_fit(capacity, data):
    attendees = data.draw(st.integers(min_value=1, max_value=capacity))
    validate_attendees_fit_room(attendees, capacity)


@pytest.mark.req("US-10")
@given(capacity=st.integers(min_value=1, max_value=10_000), extra=st.integers(min_value=1, max_value=10_000))
def test_attendees_over_capacity_never_fit(capacity, extra):
    with pytest.raises(BookingRuleError):
        validate_attendees_fit_room(capacity + extra, capacity)
