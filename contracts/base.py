"""Forbid undeclared fields on all contract objects."""

from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")
