from datetime import datetime


def format_duration(start_date: datetime, stop_date: datetime) -> str:
    """Format the duration between two dates in a human-readable format"""
    if not start_date or not stop_date:
        return "-"

    duration = stop_date - start_date
    total_seconds = int(duration.total_seconds())

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"
