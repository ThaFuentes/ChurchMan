# date_helpers.py

from datetime import datetime, date

# Standard date format for your database (adjust if your DB uses a different format)
STANDARD_DATE_FORMAT = '%Y-%m-%d'


def parse_date(date_str, format=STANDARD_DATE_FORMAT):
    """
    Parse a date string into a Python date object.
    Returns None if parsing fails.

    :param date_str: Date string (e.g., '2025-03-07')
    :param format: Format to parse (default is '%Y-%m-%d')
    :return: date object or None if invalid
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, format).date()
    except ValueError:
        return None


def format_date(date_obj, format=STANDARD_DATE_FORMAT):
    """
    Format a Python date object into a string.
    Returns an empty string if the date object is invalid.

    :param date_obj: Date object
    :param format: Format to use (default is '%Y-%m-%d')
    :return: formatted date string
    """
    if not date_obj or not isinstance(date_obj, (datetime, date)):
        return ''
    return date_obj.strftime(format)


def today_string(format=STANDARD_DATE_FORMAT):
    """
    Get today's date as a string.

    :param format: Format to use (default is '%Y-%m-%d')
    :return: today's date as string
    """
    return datetime.now().strftime(format)


def is_valid_date(date_str, format=STANDARD_DATE_FORMAT):
    """
    Check if a string is a valid date.

    :param date_str: Date string to validate
    :param format: Expected format (default '%Y-%m-%d')
    :return: True if valid, False if not
    """
    return parse_date(date_str, format) is not None
