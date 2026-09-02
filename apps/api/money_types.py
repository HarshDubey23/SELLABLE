# -*- coding: utf-8 -*-
"""
Strict Money Type abstraction for SELLABLE.

Rules:
- Integer paise internally (1 INR = 100 paise)
- Explicit INR currency
- No float arithmetic in financial calculations
- Immutable dataclass
- Strict boundary and validation checks
"""
from dataclasses import dataclass
from typing import Any

class MoneyError(ValueError):
    pass

@dataclass(frozen=True)
class Money:
    paise: int
    currency: str = "INR"

    def __post_init__(self):
        if not isinstance(self.paise, int):
            raise MoneyError(f"Amount must be an integer paise amount, got {type(self.paise).__name__}")
        if self.paise < 0:
            raise MoneyError(f"Negative money amount is not allowed: {self.paise}")
        if self.currency != "INR":
            raise MoneyError(f"Unsupported currency: {self.currency}. Only INR is supported.")

    @classmethod
    def from_inr(cls, inr_amount: int | str) -> "Money":
        """Construct from whole INR amount (must be int or string integer)."""
        if isinstance(inr_amount, float):
            raise MoneyError("Floating point INR input is forbidden. Use integer paise or integer INR.")
        return cls(paise=int(inr_amount) * 100, currency="INR")

    @classmethod
    def from_paise(cls, paise_amount: int) -> "Money":
        return cls(paise=paise_amount, currency="INR")

    def to_inr(self) -> float:
        return self.paise / 100.0

    def format_inr(self) -> str:
        return f"Rs {self.paise / 100:,.2f}"

    def __add__(self, other: Any) -> "Money":
        if not isinstance(other, Money):
            raise MoneyError("Cannot add non-Money to Money")
        if self.currency != other.currency:
            raise MoneyError(f"Currency mismatch: {self.currency} vs {other.currency}")
        return Money(paise=self.paise + other.paise, currency=self.currency)

    def __sub__(self, other: Any) -> "Money":
        if not isinstance(other, Money):
            raise MoneyError("Cannot subtract non-Money from Money")
        if self.currency != other.currency:
            raise MoneyError(f"Currency mismatch: {self.currency} vs {other.currency}")
        if self.paise < other.paise:
            raise MoneyError(f"Subtraction would result in negative money: {self.paise} - {other.paise}")
        return Money(paise=self.paise - other.paise, currency=self.currency)

    def __mul__(self, factor: int) -> "Money":
        if not isinstance(factor, int):
            raise MoneyError(f"Multiplication factor must be an integer, got {type(factor).__name__}")
        if factor < 0:
            raise MoneyError("Multiplication factor cannot be negative")
        return Money(paise=self.paise * factor, currency=self.currency)

    def __lt__(self, other: "Money") -> bool:
        if not isinstance(other, Money) or self.currency != other.currency:
            raise MoneyError("Invalid comparison")
        return self.paise < other.paise

    def __le__(self, other: "Money") -> bool:
        if not isinstance(other, Money) or self.currency != other.currency:
            raise MoneyError("Invalid comparison")
        return self.paise <= other.paise

    def __gt__(self, other: "Money") -> bool:
        if not isinstance(other, Money) or self.currency != other.currency:
            raise MoneyError("Invalid comparison")
        return self.paise > other.paise

    def __ge__(self, other: "Money") -> bool:
        if not isinstance(other, Money) or self.currency != other.currency:
            raise MoneyError("Invalid comparison")
        return self.paise >= other.paise
