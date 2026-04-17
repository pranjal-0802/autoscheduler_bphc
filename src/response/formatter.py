"""
Response formatting utilities.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from src.models.job import Job, JobResult, ScheduleResult, InfeasibilityInfo
from src.models.enums import JobStatus


@dataclass
class SubmitResponse:
    """Response for job submission."""

    job_id: str


@dataclass
class StatusResponse:
    """Response for job status query."""

    status: str


@dataclass
class SectionAllotmentResponse:
    """Response format for a section's allotment."""

    room: str
    slots: list[str]


@dataclass
class InfeasibilityResponse:
    """Response format for infeasibility information."""

    problematic_courses: list[str] = field(default_factory=list)
    conflicting_constraints: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class ResultResponse:
    """Response for completed job result."""

    timetable: Optional[dict[str, dict[str, dict[str, Any]]]] = None
    error: Optional[str] = None
    infeasibility_info: Optional[dict[str, Any]] = None
    solve_time_seconds: Optional[float] = None


@dataclass
class ErrorResponse:
    """Response for error conditions."""

    detail: str


class ResponseFormatter:
    """Formats internal data structures to API responses."""

    @staticmethod
    def format_submit_response(job_id: str) -> dict[str, Any]:
        """
        Format a job submission response.

        Args:
            job_id: The unique job identifier.

        Returns:
            Dictionary suitable for JSON response.
        """
        return {"job_id": job_id}

    @staticmethod
    def format_status_response(job: Job) -> dict[str, Any]:
        """
        Format a job status response.

        Args:
            job: The job to get status for.

        Returns:
            Dictionary suitable for JSON response.
        """
        return {"status": job.status.value}

    @staticmethod
    def format_result_response(job: Job) -> dict[str, Any]:
        """
        Format a completed job result response.

        Args:
            job: The completed job.

        Returns:
            Dictionary suitable for JSON response.
        """
        if job.status != JobStatus.COMPLETED and job.status != JobStatus.FAILED:
            return {"error": f"Job is not complete. Current status: {job.status.value}"}

        if job.result is None:
            return {"error": "No result available"}

        response: dict[str, Any] = {}

        if job.result.schedule is not None:
            response["timetable"] = ResponseFormatter._format_timetable(
                job.result.schedule
            )

        if job.result.error is not None:
            response["error"] = job.result.error

        if job.result.infeasibility_info is not None:
            response["infeasibility_info"] = ResponseFormatter._format_infeasibility(
                job.result.infeasibility_info
            )

        if job.result.solve_time_seconds is not None:
            response["solve_time_seconds"] = job.result.solve_time_seconds

        return response

    @staticmethod
    def _format_timetable(schedule: ScheduleResult) -> dict[str, dict[str, dict[str, Any]]]:
        """Format the timetable from a ScheduleResult."""
        timetable: dict[str, dict[str, dict[str, Any]]] = {}

        for course_code, sections in schedule.timetable.items():
            timetable[course_code] = {}
            for section_id, allotment in sections.items():
                timetable[course_code][section_id] = {
                    "room": allotment.room,
                    "slots": allotment.slots,
                }

        return timetable

    @staticmethod
    def _format_infeasibility(info: InfeasibilityInfo) -> dict[str, Any]:
        """Format infeasibility information."""
        return {
            "problematic_courses": info.problematic_courses,
            "conflicting_constraints": info.conflicting_constraints,
            "suggestions": info.suggestions,
        }

    @staticmethod
    def format_validation_errors(errors: list[Any]) -> dict[str, Any]:
        """
        Format validation errors response.

        Args:
            errors: List of validation errors.

        Returns:
            Dictionary suitable for JSON response.
        """
        return {
            "detail": "Validation failed",
            "errors": [
                {
                    "field": err.field,
                    "message": err.message,
                    "value": str(err.value) if err.value is not None else None,
                }
                for err in errors
            ],
        }
