from datetime import time


def is_valid_lesson_duration(start_time: time, end_time: time) -> bool:
    """Перевіряє, чи час початку передує часу завершення."""
    return start_time < end_time
