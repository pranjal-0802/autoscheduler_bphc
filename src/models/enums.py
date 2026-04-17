"""
Enumerations used throughout the scheduler application.
"""

from enum import Enum


class JobStatus(Enum):
    """Status of a scheduling job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ClassType(Enum):
    """Type of class session."""

    LECTURE = "L"
    TUTORIAL = "T"
    PRACTICAL = "P"


class CourseType(Enum):
    """Type of course based on its target audience."""

    CDC = "CDC"
    DEL = "DEL"
    HUEL = "HUEL"
