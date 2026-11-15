"""Reject undeclared data at contract boundaries."""

import pytest
from pydantic import ValidationError

from contracts.base import Contract


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Contract(secret="undeclared")
