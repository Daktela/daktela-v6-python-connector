"""Small data-formatting helpers used by Daktela integrations."""

from typing import Optional


def normalize_phone_number(
    number: Optional[str],
    *,
    plus_sign: bool = False,
    international_prefix: str = "420",
    international_length: int = 12,
) -> Optional[str]:
    """Normalize a phone number to an international ``00`` or ``+`` form.

    Args:
        number: Phone number to normalize, or ``None``.
        plus_sign: Use ``+`` instead of ``00`` for the international marker.
        international_prefix: Country calling prefix used for local numbers.
        international_length: Minimum length at which a number beginning with
            ``international_prefix`` is already considered international.
    """
    if number is None:
        return None
    if not international_prefix:
        raise ValueError("international_prefix must not be empty")
    if international_length <= 0:
        raise ValueError("international_length must be greater than zero")

    value = "".join(number.split())
    marker = "+" if plus_sign else "00"

    if value.startswith("+"):
        value = value[1:]
    elif value.startswith("00"):
        value = value[2:]
    elif not (
        value.startswith(international_prefix) and len(value) >= international_length
    ):
        value = international_prefix + value
    return marker + value
