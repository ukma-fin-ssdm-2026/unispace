"""
Модуль для перевірки бізнес-правил (Lab06).
Примітка щодо використання ШІ: код розроблено з допомогою ШІ-асистента
в рамках демонстрації мікроциклів TDD.
"""

from datetime import time

MAX_LESSON_MINUTES = 90


def is_valid_lesson_duration(start_time: time, end_time: time) -> bool:
    """Перевіряє, що час заняття коректний і не перевищує ліміт."""
    if start_time >= end_time:
        return False

    duration_minutes = (end_time.hour * 60 + end_time.minute) - (start_time.hour * 60 + start_time.minute)
    return duration_minutes <= MAX_LESSON_MINUTES
