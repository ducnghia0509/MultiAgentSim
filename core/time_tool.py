import datetime
import pytz

def get_current_time_vn():
    """Get current time in Vietnam timezone."""
    vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    return datetime.datetime.now(vn_tz).strftime("%Y-%m-%d %H:%M:%S %Z")

def format_timestamp(timestamp: str):
    """Format a timestamp string."""
    try:
        dt = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
        dt_vn = dt.astimezone(vn_tz)
        return dt_vn.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception as e:
        print(f"Error formatting timestamp {timestamp}: {e}")
        return timestamp