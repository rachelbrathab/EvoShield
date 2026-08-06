"""Contract tests for the AnalysisStatus enum (Sprint 3 preparation)."""

import pytest
from pydantic import BaseModel, ValidationError

from app.models.repository import AnalysisStatus


def test_all_expected_states_present() -> None:
    """The full lifecycle vocabulary must be defined, in canonical order."""
    assert [s.value for s in AnalysisStatus] == [
        "not_analyzed",
        "queued",
        "analyzing",
        "analyzed",
        "failed",
        "cancelled",
    ]


def test_status_is_string_enum() -> None:
    """Values serialize as their canonical snake_case strings."""
    assert AnalysisStatus.NOT_ANALYZED.value == "not_analyzed"
    assert str(AnalysisStatus.ANALYZING) == "analyzing"
    assert AnalysisStatus("analyzed") is AnalysisStatus.ANALYZED


def test_status_round_trips_through_json() -> None:
    """API responses must carry the plain string value, not a nested object."""

    class Payload(BaseModel):
        status: AnalysisStatus

    assert Payload(status=AnalysisStatus.QUEUED).model_dump_json() == ('{"status":"queued"}')
    assert Payload.model_validate({"status": "analyzed"}).status is AnalysisStatus.ANALYZED


def test_unknown_status_rejected() -> None:
    """Free-form strings are not accepted at the contract boundary."""

    class Payload(BaseModel):
        status: AnalysisStatus

    with pytest.raises(ValidationError):
        Payload.model_validate({"status": "running-something-else"})
