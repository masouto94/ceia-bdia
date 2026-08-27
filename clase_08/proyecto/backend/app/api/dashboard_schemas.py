"""Validated read contracts for the tenant dashboard."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

DashboardStatus = Literal["draft", "running", "completed", "failed"]
DashboardSort = Literal["created_at:desc", "created_at:asc", "name:asc", "name:desc", "result_count:desc"]


class DashboardQuery(BaseModel):
    from_date: date
    to_date: date
    search: str = Field(default="", max_length=120)
    status: DashboardStatus | Literal[""] = ""
    sort: DashboardSort = "created_at:desc"
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def bounded_range(self) -> "DashboardQuery":
        if self.to_date < self.from_date:
            raise ValueError("La fecha final debe ser posterior a la inicial.")
        if (self.to_date - self.from_date).days > 365:
            raise ValueError("El rango máximo es de 366 días.")
        return self
