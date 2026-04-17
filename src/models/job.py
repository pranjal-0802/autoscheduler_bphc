"""
Job-related data models for tracking scheduling tasks.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

from src.models.enums import JobStatus


@dataclass
class SectionAllotment:
    """
    Allotment result for a single section.

    Attributes:
        room: The assigned room.
        slots: List of assigned time slots.
    """

    room: str
    slots: list[str]


@dataclass
class ScheduleResult:
    """
    Complete scheduling result for all courses.

    Maps course codes to their section allotments.
    """

    timetable: dict[str, dict[str, SectionAllotment]]


@dataclass
class InfeasibilityInfo:
    """
    Information about why a scheduling problem is infeasible.

    Attributes:
        problematic_courses: List of course codes that may be causing issues.
        conflicting_constraints: Description of conflicting constraints.
        suggestions: Suggestions for resolving the infeasibility.
    """

    problematic_courses: list[str] = field(default_factory=list)
    conflicting_constraints: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class JobResult:
    """
    Result of a scheduling job.

    Attributes:
        schedule: The computed timetable (if successful).
        error: Error message (if failed).
        infeasibility_info: Information about why the problem is infeasible (if applicable).
        solve_time_seconds: Time taken to solve in seconds.
        solver_stats: Additional solver statistics.
    """

    schedule: Optional[ScheduleResult] = None
    error: Optional[str] = None
    infeasibility_info: Optional[InfeasibilityInfo] = None
    solve_time_seconds: Optional[float] = None
    solver_stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class Job:
    """
    A scheduling job.

    Attributes:
        id: Unique job identifier.
        status: Current job status.
        created_at: When the job was created.
        started_at: When processing started.
        completed_at: When processing completed.
        request_data: The original request data.
        result: The job result (when completed or failed).
    """

    id: str
    status: JobStatus
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    request_data: Optional[dict[str, Any]] = None
    result: Optional[JobResult] = None
