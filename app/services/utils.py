import re
from typing import Optional


def normalize_nit(value: Optional[str]) -> Optional[str]:
    """Normalize Colombian NIT: remove any non-digit chars and strip verifier digit (DV).

    Examples:
    - "900123456-7" -> "900123456"
    - "900.123.456-7" -> "900123456"
    - None -> None
    """
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    # Strip last digit (DV) if there is more than one digit
    if len(digits) > 1:
        return digits[:-1]
    return digits
