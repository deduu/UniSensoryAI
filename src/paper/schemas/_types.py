"""Portable JSON scalar types shared by PAPER extraction contracts."""

from typing import Annotated

from pydantic import Field, StringConstraints

Text = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=4000, pattern=r"\S"
    ),
]
Identity = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=256, pattern=r"\S"
    ),
]
Currency = Annotated[
    str, StringConstraints(strict=True, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
]
DecimalString = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=1,
        max_length=100,
        pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$",
    ),
]
PositiveInteger = Annotated[int, Field(strict=True, gt=0)]
