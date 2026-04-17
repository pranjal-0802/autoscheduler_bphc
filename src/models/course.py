"""
Course-related data models.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Section:
    """
    A section of a class type (lecture, tutorial, or practical).

    Attributes:
        id: Section identifier (e.g., 'L1', 'T2', 'P3').
        instructors: List of instructor names for this section.
        preferred_rooms: List of preferred room names for this section.
    """

    id: str
    instructors: list[str] = field(default_factory=list)
    preferred_rooms: list[str] = field(default_factory=list)


@dataclass
class ClassSpec:
    """
    Specification for a type of class (lecture, tutorial, or practical).

    Attributes:
        duration: Number of consecutive hours for one session.
        perweek: Number of sessions per week.
        sections: List of sections for this class type.
    """

    duration: int
    perweek: int
    sections: list[Section] = field(default_factory=list)


@dataclass
class CourseAllotment:
    """
    Allotment details for an already scheduled course.

    Maps section IDs to their assigned time slots.
    """

    slots: dict[str, list[str]]


@dataclass
class AllottedCourse:
    """
    A course that has already been scheduled.

    Attributes:
        code: Course code (e.g., 'CS F342').
        branches: List of branch groups this course is offered to.
        pattern_year: The year pattern for slot allocation ('1', '2', '3', '4', 'D', 'H').
        L: Lecture specification (optional).
        T: Tutorial specification (optional).
        P: Practical specification (optional).
        allotment: The actual slot allocations for each section.
    """

    code: str
    branches: list[str]
    pattern_year: str
    allotment: CourseAllotment
    L: Optional[ClassSpec] = None
    T: Optional[ClassSpec] = None
    P: Optional[ClassSpec] = None


@dataclass
class CourseToSchedule:
    """
    A course that needs to be scheduled.

    Attributes:
        code: Course code (e.g., 'CS F345').
        branches: List of branch groups this course is offered to.
        pattern_year: The year pattern for slot allocation ('1', '2', '3', '4', 'D', 'H').
        L: Lecture specification (optional).
        T: Tutorial specification (optional).
        P: Practical specification (optional).
    """

    code: str
    branches: list[str]
    pattern_year: str
    L: Optional[ClassSpec] = None
    T: Optional[ClassSpec] = None
    P: Optional[ClassSpec] = None

    def get_course_type(self) -> str:
        """
        Determine the course type based on pattern_year.

        Returns:
            'CDC' for years 1-4, 'DEL' for 'D', 'HUEL' for 'H'.
        """
        if self.pattern_year in ("1", "2", "3", "4"):
            return "CDC"
        elif self.pattern_year == "D":
            return "DEL"
        elif self.pattern_year == "H":
            return "HUEL"
        return "CDC"
