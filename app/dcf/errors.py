class ValuationError(Exception):
    """Raised for expected, user-facing failures (bad ticker, bad Excel
    file, no shares, etc). Routes catch this specifically to flash a
    clean message; anything else falls through to a generic 500-safe
    handler."""
