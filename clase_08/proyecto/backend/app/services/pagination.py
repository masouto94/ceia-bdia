"""Bounded pagination contracts; authorization remains with the caller's RLS transaction."""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PageRequest:
    page: int = 1
    per_page: int = 20

    def __post_init__(self) -> None:
        if self.page < 1 or self.per_page not in {10, 20, 50}:
            raise ValueError("invalid pagination")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int

    @property
    def pages(self) -> int:
        return (self.total + self.per_page - 1) // self.per_page
