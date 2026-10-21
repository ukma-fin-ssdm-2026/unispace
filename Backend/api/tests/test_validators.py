from datetime import time
from api.validators import is_valid_lesson_duration


def test_inverted_times_returns_false():
    # Arrange
    start = time(10, 30)
    end = time(9, 0)

    # Act
    result = is_valid_lesson_duration(start, end)

    # Assert
    assert result is False


def test_duration_exceeds_limit_returns_false():
    # Arrange: різниця 120 хвилин
    start = time(10, 0)
    end = time(12, 0)

    # Act
    result = is_valid_lesson_duration(start, end)

    # Assert
    assert result is False
