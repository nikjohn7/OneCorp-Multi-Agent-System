"""
Date Resolver Utilities

This module provides utilities to resolve human-readable appointment phrases
(e.g., "Thursday at 11:30am") into concrete timezone-aware datetime objects.
"""

import re
from datetime import datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo


# Weekday name to day-of-week number (Monday=0, Sunday=6)
WEEKDAY_MAP = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}


def resolve_appointment_phrase(
    base_dt: datetime,
    phrase: str,
    tz: ZoneInfo | str = "Australia/Melbourne"
) -> Optional[datetime]:
    """
    Convert a human appointment phrase into a concrete timezone-aware datetime.

    Supports patterns like:
    - "Thursday at 11:30am"
    - "Friday at 2:00pm"
    - "Monday at 9am"

    The function finds the next occurrence of the specified weekday after the base_dt
    and combines it with the parsed time.

    Args:
        base_dt: Reference datetime (typically email timestamp)
        phrase: Human-readable appointment phrase (e.g., "Thursday at 11:30am")
        tz: Timezone as string or ZoneInfo object (default: Australia/Melbourne)

    Returns:
        Resolved timezone-aware datetime, or None if phrase cannot be parsed

    Examples:
        >>> base = datetime(2025, 1, 14, 9, 12, tzinfo=ZoneInfo("Australia/Melbourne"))
        >>> resolve_appointment_phrase(base, "Thursday at 11:30am")
        datetime.datetime(2025, 1, 16, 11, 30, tzinfo=zoneinfo.ZoneInfo(key='Australia/Melbourne'))
    """
    if not phrase:
        return None

    # Normalize timezone
    if isinstance(tz, str):
        tz = ZoneInfo(tz)

    # Ensure base_dt is timezone-aware
    if base_dt.tzinfo is None:
        base_dt = base_dt.replace(tzinfo=tz)

    # Pattern: "<weekday> at <time>"
    # Matches: "Thursday at 11:30am", "Friday at 2pm", "Monday at 9:00 AM"
    pattern = r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+(\d{1,2})(?:[:\.](\d{2}))?\s*(am|pm)?\b'

    match = re.search(pattern, phrase, re.IGNORECASE)
    if not match:
        return None

    day_name = match.group(1).lower()
    hour_str = match.group(2)
    minute_str = match.group(3) or "00"  # Default to :00 if not specified
    am_pm = match.group(4).lower() if match.group(4) else None

    # Parse hour and minute
    try:
        hour = int(hour_str)
        minute = int(minute_str)
    except (ValueError, TypeError):
        return None

    # Convert 12-hour to 24-hour format if am/pm specified
    if am_pm:
        if am_pm == 'pm' and hour != 12:
            hour += 12
        elif am_pm == 'am' and hour == 12:
            hour = 0

    # Validate time components
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    # Create time object
    try:
        appointment_time = time(hour, minute)
    except ValueError:
        return None

    # Find the next occurrence of the target weekday
    target_weekday = WEEKDAY_MAP[day_name]
    current_weekday = base_dt.weekday()

    # Calculate days until target weekday
    days_ahead = target_weekday - current_weekday

    # If the weekday is today or in the past this week, move to next week
    if days_ahead <= 0:
        days_ahead += 7

    # Calculate target date
    target_date = base_dt.date() + timedelta(days=days_ahead)

    # Combine date and time with timezone
    appointment_dt = datetime.combine(target_date, appointment_time, tzinfo=tz)

    return appointment_dt


def parse_time_string(time_str: str) -> Optional[time]:
    """
    Parse a time string like "11:30am" or "2pm" into a time object.

    Args:
        time_str: Time string (e.g., "11:30am", "2pm", "9:00 AM")

    Returns:
        Parsed time object, or None if parsing fails

    Examples:
        >>> parse_time_string("11:30am")
        datetime.time(11, 30)
        >>> parse_time_string("2pm")
        datetime.time(14, 0)
    """
    if not time_str:
        return None

    # Pattern for time: HH:MM or HH with optional am/pm
    pattern = r'(\d{1,2})(?:[:\.](\d{2}))?\s*(am|pm)?'

    match = re.search(pattern, time_str.strip(), re.IGNORECASE)
    if not match:
        return None

    hour_str = match.group(1)
    minute_str = match.group(2) or "00"
    am_pm = match.group(3).lower() if match.group(3) else None

    try:
        hour = int(hour_str)
        minute = int(minute_str)
    except (ValueError, TypeError):
        return None

    # Convert 12-hour to 24-hour format if am/pm specified
    if am_pm:
        if am_pm == 'pm' and hour != 12:
            hour += 12
        elif am_pm == 'am' and hour == 12:
            hour = 0

    # Validate and create time object
    try:
        return time(hour, minute)
    except ValueError:
        return None
