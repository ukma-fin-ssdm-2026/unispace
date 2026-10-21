from datetime import time


def is_valid_lesson_duration(start_time: time, end_time: time) -> bool:
    """Перевіряє тривалість пари."""
    if start_time >= end_time:
        return False

    duration_minutes = (end_time.hour * 60 + end_time.minute) - (start_time.hour * 60 + start_time.minute)
    return duration_minutes <= 90
