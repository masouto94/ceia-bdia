"""Typed experiment HTTP contracts."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

ExperimentStatus = Literal["draft", "running", "completed", "failed"]
MetricType = Literal["number", "text", "boolean", "json"]


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class ExperimentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: ExperimentStatus | None = None
    archived: bool | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return ExperimentCreate.strip_name(value)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("reason must not be blank")
        return value

    @model_validator(mode="after")
    def validate_update(self) -> "ExperimentUpdate":
        if self.reason is not None and self.status is None:
            raise ValueError("reason requires a status change")
        if self.name is None and self.status is None and self.archived is None:
            raise ValueError("an update requires name, status, or archived")
        return self


class MetricCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: MetricType
    value: Any
    unit: str | None = Field(default=None, max_length=40)
    step: int | None = Field(default=None, ge=0)
    timestamp: datetime | None = None

    @model_validator(mode="after")
    def typed_value(self):
        valid = {
            "number": isinstance(self.value, (int, float)) and not isinstance(self.value, bool),
            "text": isinstance(self.value, str),
            "boolean": isinstance(self.value, bool),
            "json": isinstance(self.value, (dict, list)),
        }
        if not valid[self.type]:
            raise ValueError("metric value does not match type")
        return self


class ResultCreate(BaseModel):
    status: Literal["completed", "failed"]
    terminal_status: Literal["completed", "failed"] | None = None
    transition_reason: str | None = Field(default=None, min_length=1, max_length=1000)
    input_summary: str | None = Field(default=None, max_length=4000)
    output_summary: str | None = Field(default=None, max_length=4000)
    metrics: list[MetricCreate] = Field(default_factory=list, max_length=100)

    @field_validator("transition_reason", mode="before")
    @classmethod
    def strip_transition_reason(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("transition_reason must not be blank")
        return value

    @model_validator(mode="after")
    def transition_reason_requires_terminal_status(self) -> "ResultCreate":
        if self.transition_reason is not None and self.terminal_status is None:
            raise ValueError("transition_reason requires terminal_status")
        return self


class ExperimentPath(BaseModel):
    experiment_id: UUID
