"""
Internal data structures for the solver.
"""

from dataclasses import dataclass, field
from typing import Any

from ortools.sat.python import cp_model


@dataclass
class SectionVariable:
    """
    Variables for a single section assignment.

    Attributes:
        course_code: The course this section belongs to.
        section_id: The section identifier (e.g., 'L1', 'T2').
        class_type: Type of class ('L', 'T', 'P').
        slot_vars: Boolean variables for each potential slot assignment.
        room_var: Integer variable for room assignment.
        pattern_slot_var: Integer variable for which pattern slot is chosen.
        instructors: List of instructor names.
        preferred_rooms: List of preferred room names.
        duration: Duration in hours per session.
        sessions_per_week: Number of sessions per week.
    """

    course_code: str
    section_id: str
    class_type: str
    slot_vars: dict[int, cp_model.IntVar] = field(default_factory=dict)
    room_var: cp_model.IntVar | None = None
    pattern_slot_var: cp_model.IntVar | None = None
    instructors: list[str] = field(default_factory=list)
    preferred_rooms: list[str] = field(default_factory=list)
    duration: int = 1
    sessions_per_week: int = 1
    pattern_options: list[tuple[str, list[int]]] = field(default_factory=list)


@dataclass
class CourseVariables:
    """
    All variables for a single course.

    Attributes:
        code: Course code.
        branches: Branch groups this course is for.
        pattern_year: The slot pattern year.
        lecture_sections: Variables for lecture sections.
        tutorial_sections: Variables for tutorial sections.
        practical_sections: Variables for practical sections.
    """

    code: str
    branches: list[str]
    pattern_year: str
    lecture_sections: list[SectionVariable] = field(default_factory=list)
    tutorial_sections: list[SectionVariable] = field(default_factory=list)
    practical_sections: list[SectionVariable] = field(default_factory=list)

    def all_sections(self) -> list[SectionVariable]:
        """Return all sections across all class types."""
        return self.lecture_sections + self.tutorial_sections + self.practical_sections


@dataclass
class AllottedSection:
    """
    Represents an already allotted section.

    Attributes:
        course_code: The course this section belongs to.
        section_id: The section identifier.
        class_type: Type of class ('L', 'T', 'P').
        slots: List of assigned time slot indices.
        instructors: List of instructor names.
        room: Assigned room (if known).
    """

    course_code: str
    section_id: str
    class_type: str
    slots: list[int]
    instructors: list[str] = field(default_factory=list)
    room: str | None = None


@dataclass
class SolverContext:
    """
    Context containing all solver data and mappings.

    Attributes:
        model: The CP-SAT model.
        course_variables: Variables for courses to schedule.
        allotted_sections: Pre-allotted sections.
        room_to_index: Mapping from room name to index.
        index_to_room: Mapping from index to room name.
        all_rooms: Set of all room names.
        instructor_sections: Mapping from instructor to their sections.
        branch_courses: Mapping from branch to courses for that branch.
        constraint_names: Names of constraints for infeasibility analysis.
    """

    model: cp_model.CpModel
    course_variables: dict[str, CourseVariables] = field(default_factory=dict)
    allotted_sections: list[AllottedSection] = field(default_factory=list)
    room_to_index: dict[str, int] = field(default_factory=dict)
    index_to_room: dict[int, str] = field(default_factory=dict)
    all_rooms: set[str] = field(default_factory=set)
    instructor_sections: dict[str, list[SectionVariable | AllottedSection]] = field(
        default_factory=dict
    )
    branch_courses: dict[str, list[str]] = field(default_factory=dict)
    constraint_names: dict[int, str] = field(default_factory=dict)
    pattern_slots: dict[str, dict[str, list[int]]] = field(default_factory=dict)

    def add_constraint_name(self, constraint: Any, name: str) -> None:
        """Track a constraint by name for infeasibility analysis."""
        if hasattr(constraint, "Index"):
            self.constraint_names[constraint.Index()] = name
