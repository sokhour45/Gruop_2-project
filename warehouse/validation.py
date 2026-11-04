"""Validation functions and the common UI retry gate."""

from dataclasses import dataclass
import math
import re
from typing import Callable, Generator, Mapping, Sequence


CATEGORIES = (
    "Electronics",
    "Food",
    "Office Supplies",
    "Packaging",
    "Tools",
    "Other",
)
UNITS = ("pcs", "box", "kg")


@dataclass(frozen=True)
class FieldError:
    field: str
    message: str


def validate_product(
    values: Mapping[str, str],
    sku_exists: Callable[[str], bool],
) -> tuple[dict[str, object], list[FieldError]]:
    """Return normalized values and every field-specific error."""
    cleaned = {key: value.strip() for key, value in values.items()}
    errors: list[FieldError] = []

    sku = cleaned.get("sku", "")
    if not sku:
        errors.append(FieldError("sku", "SKU is required."))
    elif not re.fullmatch(r"[A-Za-z0-9]+", sku):
        errors.append(FieldError("sku", "SKU must contain letters and numbers only."))
    elif sku_exists(sku):
        errors.append(FieldError("sku", "That SKU is already in use."))

    name = cleaned.get("name", "")
    if len(name) < 2:
        errors.append(FieldError("name", "Name is required and must be at least 2 characters."))

    category = cleaned.get("category", "")
    if category not in CATEGORIES:
        errors.append(FieldError("category", "Choose a category from the list."))

    unit = cleaned.get("unit", "")
    if unit not in UNITS:
        errors.append(FieldError("unit", "Choose a unit from the list."))

    price_text = cleaned.get("unit_price", "")
    try:
        price = float(price_text)
        if price < 0 or not math.isfinite(price):
            raise ValueError
    except ValueError:
        errors.append(FieldError("unit_price", "Enter a number greater than or equal to 0."))
        price = 0.0

    quantity = _nonnegative_integer(cleaned.get("quantity", ""), "quantity", errors)
    reorder_level = _nonnegative_integer(
        cleaned.get("reorder_level", ""), "reorder_level", errors
    )

    if errors:
        return {}, errors

    return {
        "sku": sku,
        "name": name,
        "category": category,
        "unit": unit,
        "unit_price": price,
        "quantity": quantity,
        "reorder_level": reorder_level,
        "supplier": cleaned.get("supplier", ""),
        "location": cleaned.get("location", ""),
    }, []


def _nonnegative_integer(
    value: str, field: str, errors: list[FieldError]
) -> int:
    if not re.fullmatch(r"\d+", value):
        errors.append(FieldError(field, "Enter a whole number greater than or equal to 0."))
        return 0
    return int(value)


def validate_movement(
    quantity_text: str, movement_type: str, available: int | None = None
) -> tuple[int | None, list[FieldError]]:
    errors: list[FieldError] = []
    if not re.fullmatch(r"\d+", quantity_text.strip()):
        return None, [FieldError("quantity", "Enter a whole number greater than 0.")]
    quantity = int(quantity_text.strip())
    if quantity <= 0:
        errors.append(FieldError("quantity", "Quantity must be greater than 0."))
    elif movement_type == "OUT" and available is not None and quantity > available:
        errors.append(
            FieldError(
                "quantity",
                f"Only {available} available; enter a quantity no greater than {available}.",
            )
        )
    return (None, errors) if errors else (quantity, [])


def validation_gate(
    validate: Callable[[], tuple[bool, Sequence[FieldError]]],
    show_errors: Callable[[Sequence[FieldError]], None],
    focus_field: Callable[[str], None],
) -> Generator[bool, None, bool]:
    """Validate a submission; failures keep the active form open for retry.

    The generator yields after an invalid attempt so Tkinter can process user
    input. The next Save/Submit resumes this loop and validates all fields again.
    """
    while True:
        valid, errors = validate()
        if valid:
            return True
        show_errors(errors)
        if errors:
            focus_field(errors[0].field)
        yield False
