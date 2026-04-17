"""
Request models for the scheduling API.
"""

from dataclasses import dataclass, field
from typing import Optional, Any

from pydantic import BaseModel, Field


class SectionModel(BaseModel):
    """Pydantic model for section input."""

    id: str
    instructors: list[str] = Field(default_factory=list)
    preferredRooms: list[str] = Field(default_factory=list)


class ClassSpecModel(BaseModel):
    """Pydantic model for class specification input."""

    duration: int = Field(ge=1, le=4)
    perweek: int = Field(ge=0, le=10)
    sections: list[SectionModel] = Field(default_factory=list)


class AllottedCourseModel(BaseModel):
    """Pydantic model for an already allocated course."""

    code: str
    branches: list[str]
    patternYear: str
    L: Optional[ClassSpecModel] = None
    T: Optional[ClassSpecModel] = None
    P: Optional[ClassSpecModel] = None
    allotment: dict[str, list[str]]


class CourseToScheduleModel(BaseModel):
    """Pydantic model for a course to be scheduled."""

    code: str
    branches: list[str]
    patternYear: str
    L: Optional[ClassSpecModel] = None
    T: Optional[ClassSpecModel] = None
    P: Optional[ClassSpecModel] = None


class ScheduleRequestModel(BaseModel):
    """Pydantic model for the schedule request payload."""

    allotted: list[AllottedCourseModel] = Field(default_factory=list)
    toschedule: list[CourseToScheduleModel]
    patterns: dict[str, dict[str, list[str]]]


@dataclass
class SlotPatterns:
    """
    Slot patterns for different year groups.

    Maps pattern year (e.g., '1', '2', 'D', 'H') to pattern types
    (e.g., 'Lec1', 'Tut1') to lists of time slots.
    """

    patterns: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def get_slots_for_pattern(
        self, pattern_year: str, pattern_type: str
    ) -> list[str]:
        """
        Get the time slots for a specific pattern.

        Args:
            pattern_year: The year/type pattern (e.g., '1', '2', 'D', 'H').
            pattern_type: The pattern type (e.g., 'Lec1', 'Tut1').

        Returns:
            List of time slot strings.
        """
        if pattern_year not in self.patterns:
            return []
        return self.patterns[pattern_year].get(pattern_type, [])

    def get_all_pattern_types(self, pattern_year: str) -> list[str]:
        """
        Get all available pattern types for a year.

        Args:
            pattern_year: The year/type pattern.

        Returns:
            List of pattern type names.
        """
        if pattern_year not in self.patterns:
            return []
        return list(self.patterns[pattern_year].keys())


@dataclass
class ScheduleRequest:
    """
    Parsed schedule request data.

    Attributes:
        allotted: List of already allocated courses.
        to_schedule: List of courses to be scheduled.
        patterns: Slot patterns configuration.
    """

    allotted: list[Any]
    to_schedule: list[Any]
    patterns: SlotPatterns
