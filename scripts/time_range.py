from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def resolve_time_range(from_time="", to_time="", now=None):
    """Return the requested range in WIB, or the default daily 16:00 range."""
    zone = ZoneInfo("Asia/Jakarta")
    if bool(from_time) != bool(to_time):
        raise ValueError("--from dan --to harus diisi bersamaan (YYYY-MM-DD HH:MM:SS).")
    if from_time:
        start = datetime.strptime(from_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=zone)
        end = datetime.strptime(to_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=zone)
    else:
        end = (now or datetime.now(zone)).astimezone(zone).replace(
            hour=16, minute=0, second=0, microsecond=0
        )
        start = end - timedelta(days=1)
    if start >= end:
        raise ValueError("Waktu --from harus lebih awal daripada --to.")
    return start, end
