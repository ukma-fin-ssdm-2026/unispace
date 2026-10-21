def calculate_booking_duration(start_time, end_time):
    return int((end_time - start_time).total_seconds() / 60)
