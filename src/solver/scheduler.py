"""
Main scheduler implementation using CP-SAT solver.
"""

import multiprocessing
from dataclasses import dataclass
from typing import Any, Optional

from ortools.sat.python import cp_model

from src.models.request import ScheduleRequestModel
from src.models.job import JobResult, ScheduleResult, SectionAllotment, InfeasibilityInfo
from src.models.timeslot import TimeSlot
from src.solver.variables import (
    SolverContext,
    SectionVariable,
    CourseVariables,
    AllottedSection,
)
from src.solver.constraints import ConstraintBuilder
from src.solver.objectives import ObjectiveBuilder
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SchedulerConfig:
    """
    Configuration for the scheduler.

    Attributes:
        time_limit_seconds: Maximum time to spend solving.
        num_workers: Number of parallel workers for the solver.
        log_search_progress: Whether to log search progress.
    """

    time_limit_seconds: float = 300.0
    num_workers: int = 0
    log_search_progress: bool = True


class TimetableScheduler:
    """
    Main scheduler class that orchestrates the CP-SAT solving process.

    This class is responsible for:
    1. Converting input data to solver variables
    2. Building constraints and objectives
    3. Running the solver
    4. Extracting and formatting results
    """

    def __init__(self, config: Optional[SchedulerConfig] = None):
        """
        Initialize the scheduler.

        Args:
            config: Scheduler configuration. Uses defaults if not provided.
        """
        self.config = config or SchedulerConfig()
        self.model: Optional[cp_model.CpModel] = None
        self.solver: Optional[cp_model.CpSolver] = None
        self.context: Optional[SolverContext] = None

    def solve(self, request: ScheduleRequestModel) -> JobResult:
        """
        Solve the scheduling problem.

        Args:
            request: The schedule request containing courses and patterns.

        Returns:
            JobResult containing either the solution or error information.
        """
        logger.info("Starting scheduling process...")

        try:
            self.model = cp_model.CpModel()
            self.context = SolverContext(model=self.model)

            self._parse_patterns(request.patterns)
            self._parse_allotted_courses(request.allotted)
            self._create_variables(request.toschedule)
            self._build_instructor_mapping()
            self._build_branch_mapping(request.toschedule)

            constraint_builder = ConstraintBuilder(self.context)
            constraint_builder.build_all_constraints()

            objective_builder = ObjectiveBuilder(self.context)
            objective_builder.build_objective()

            logger.info("Model built, starting solver...")
            logger.info(f"Model stats:\n{self.model.ModelStats()}")

            self.solver = cp_model.CpSolver()
            self.solver.parameters.max_time_in_seconds = self.config.time_limit_seconds
            self.solver.parameters.log_search_progress = self.config.log_search_progress

            if self.config.num_workers > 0:
                self.solver.parameters.num_search_workers = self.config.num_workers
            else:
                self.solver.parameters.num_search_workers = max(
                    1, multiprocessing.cpu_count() - 1
                )

            status = self.solver.Solve(self.model)

            logger.info(f"Solver finished with status: {self.solver.StatusName(status)}")
            logger.info(f"Solver stats:\n{self.solver.ResponseStats()}")

            return self._process_result(status)

        except Exception as e:
            logger.exception("Error during scheduling")
            return JobResult(
                error=f"Scheduling failed: {str(e)}",
                solver_stats={"exception": str(e)},
            )

    def _parse_patterns(self, patterns: dict[str, dict[str, list[str]]]) -> None:
        """Parse slot patterns into indexed format."""
        logger.debug("Parsing slot patterns...")

        for pattern_year, pattern_types in patterns.items():
            self.context.pattern_slots[pattern_year] = {}
            for pattern_type, slots in pattern_types.items():
                slot_indices = []
                for slot_str in slots:
                    try:
                        ts = TimeSlot.from_string(slot_str)
                        slot_indices.append(ts.to_index())
                    except ValueError as e:
                        logger.warning(f"Invalid slot in pattern: {slot_str}: {e}")
                self.context.pattern_slots[pattern_year][pattern_type] = slot_indices

    def _parse_allotted_courses(self, allotted: list[Any]) -> None:
        """Parse already allotted courses."""
        logger.debug("Parsing allotted courses...")

        for course in allotted:
            for section_id, slots in course.allotment.items():
                class_type = section_id[0]
                slot_indices = []
                for slot_str in slots:
                    try:
                        ts = TimeSlot.from_string(slot_str)
                        slot_indices.append(ts.to_index())
                    except ValueError:
                        continue

                instructors = []
                spec = getattr(course, class_type, None)
                if spec and spec.sections:
                    for section in spec.sections:
                        if section.id == section_id:
                            instructors = section.instructors
                            break

                allotted_section = AllottedSection(
                    course_code=course.code,
                    section_id=section_id,
                    class_type=class_type,
                    slots=slot_indices,
                    instructors=instructors,
                )
                self.context.allotted_sections.append(allotted_section)

                for instructor in instructors:
                    if instructor not in self.context.instructor_sections:
                        self.context.instructor_sections[instructor] = []
                    self.context.instructor_sections[instructor].append(allotted_section)

    def _create_variables(self, courses: list[Any]) -> None:
        """Create CP-SAT variables for courses to schedule."""
        logger.debug("Creating variables for courses to schedule...")

        for course in courses:
            course_vars = CourseVariables(
                code=course.code,
                branches=course.branches,
                pattern_year=course.patternYear,
            )

            for class_type, attr_name in [
                ("L", "lecture_sections"),
                ("T", "tutorial_sections"),
                ("P", "practical_sections"),
            ]:
                spec = getattr(course, class_type, None)
                if spec is None or spec.perweek == 0:
                    continue

                pattern_prefix = {"L": "Lec", "T": "Tut", "P": "Pra"}[class_type]
                available_patterns = self._get_available_patterns(
                    course.patternYear, pattern_prefix
                )

                if spec.sections:
                    for section in spec.sections:
                        section_var = self._create_section_variable(
                            course.code,
                            section.id,
                            class_type,
                            section.instructors,
                            section.preferredRooms,
                            spec.duration,
                            spec.perweek,
                            available_patterns,
                        )
                        getattr(course_vars, attr_name).append(section_var)
                else:
                    section_id = f"{class_type}1"
                    section_var = self._create_section_variable(
                        course.code,
                        section_id,
                        class_type,
                        [],
                        [],
                        spec.duration,
                        spec.perweek,
                        available_patterns,
                    )
                    getattr(course_vars, attr_name).append(section_var)

            self.context.course_variables[course.code] = course_vars

    def _create_section_variable(
        self,
        course_code: str,
        section_id: str,
        class_type: str,
        instructors: list[str],
        preferred_rooms: list[str],
        duration: int,
        sessions_per_week: int,
        available_patterns: list[tuple[str, list[int]]],
    ) -> SectionVariable:
        """Create variables for a single section."""
        section_var = SectionVariable(
            course_code=course_code,
            section_id=section_id,
            class_type=class_type,
            instructors=instructors,
            preferred_rooms=preferred_rooms,
            duration=duration,
            sessions_per_week=sessions_per_week,
            pattern_options=available_patterns,
        )

        all_possible_slots = set()
        for _, slots in available_patterns:
            all_possible_slots.update(slots)

        for slot_idx in all_possible_slots:
            var_name = f"slot_{course_code}_{section_id}_{slot_idx}"
            section_var.slot_vars[slot_idx] = self.model.NewBoolVar(var_name)

        if preferred_rooms:
            for room in preferred_rooms:
                self.context.all_rooms.add(room)
                if room not in self.context.room_to_index:
                    idx = len(self.context.room_to_index)
                    self.context.room_to_index[room] = idx
                    self.context.index_to_room[idx] = room

            section_var.room_var = self.model.NewIntVar(
                0,
                len(preferred_rooms) - 1,
                f"room_{course_code}_{section_id}",
            )

        return section_var

    def _get_available_patterns(
        self, pattern_year: str, pattern_prefix: str
    ) -> list[tuple[str, list[int]]]:
        """Get available patterns for a class type."""
        patterns = []
        if pattern_year not in self.context.pattern_slots:
            return patterns

        for pattern_type, slots in self.context.pattern_slots[pattern_year].items():
            if pattern_type.startswith(pattern_prefix):
                patterns.append((pattern_type, slots))

        return patterns

    def _build_instructor_mapping(self) -> None:
        """Build mapping from instructors to their sections."""
        logger.debug("Building instructor mapping...")

        for course_vars in self.context.course_variables.values():
            for section in course_vars.all_sections():
                for instructor in section.instructors:
                    if instructor not in self.context.instructor_sections:
                        self.context.instructor_sections[instructor] = []
                    self.context.instructor_sections[instructor].append(section)

    def _build_branch_mapping(self, courses: list[Any]) -> None:
        """Build mapping from branches to courses."""
        logger.debug("Building branch mapping...")

        for course in courses:
            for branch in course.branches:
                if branch not in self.context.branch_courses:
                    self.context.branch_courses[branch] = []
                self.context.branch_courses[branch].append(course.code)

    def _process_result(self, status: int) -> JobResult:
        """Process solver result and build response."""
        solve_time = self.solver.WallTime()

        solver_stats = {
            "wall_time": solve_time,
            "user_time": self.solver.UserTime(),
            "num_booleans": self.solver.NumBooleans(),
            "num_branches": self.solver.NumBranches(),
            "num_conflicts": self.solver.NumConflicts(),
        }

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            logger.info("Solution found, extracting results...")
            schedule = self._extract_solution()

            if status == cp_model.OPTIMAL:
                solver_stats["objective_value"] = self.solver.ObjectiveValue()
                solver_stats["best_bound"] = self.solver.BestObjectiveBound()

            return JobResult(
                schedule=schedule,
                solve_time_seconds=solve_time,
                solver_stats=solver_stats,
            )

        elif status == cp_model.INFEASIBLE:
            logger.warning("Problem is infeasible")
            infeasibility_info = self._analyze_infeasibility()

            return JobResult(
                error="No feasible solution exists for the given constraints",
                infeasibility_info=infeasibility_info,
                solve_time_seconds=solve_time,
                solver_stats=solver_stats,
            )

        elif status == cp_model.MODEL_INVALID:
            validation_error = self.model.Validate()
            logger.error(f"Model is invalid: {validation_error}")

            return JobResult(
                error=f"Invalid model: {validation_error}",
                solve_time_seconds=solve_time,
                solver_stats=solver_stats,
            )

        else:
            logger.warning(f"Solver terminated with status: {self.solver.StatusName(status)}")

            return JobResult(
                error=f"Solver did not find a solution (status: {self.solver.StatusName(status)})",
                solve_time_seconds=solve_time,
                solver_stats=solver_stats,
            )

    def _extract_solution(self) -> ScheduleResult:
        """Extract the solution from solver values."""
        timetable: dict[str, dict[str, SectionAllotment]] = {}

        for course_code, course_vars in self.context.course_variables.items():
            timetable[course_code] = {}

            for section in course_vars.all_sections():
                assigned_slots = []
                for slot_idx, slot_var in section.slot_vars.items():
                    if self.solver.Value(slot_var):
                        ts = TimeSlot.from_index(slot_idx)
                        assigned_slots.append(str(ts))

                assigned_room = ""
                if section.room_var is not None and section.preferred_rooms:
                    room_idx = self.solver.Value(section.room_var)
                    if 0 <= room_idx < len(section.preferred_rooms):
                        assigned_room = section.preferred_rooms[room_idx]

                timetable[course_code][section.section_id] = SectionAllotment(
                    room=assigned_room,
                    slots=sorted(assigned_slots),
                )

        return ScheduleResult(timetable=timetable)

    def _analyze_infeasibility(self) -> InfeasibilityInfo:
        """
        Analyze the infeasible model to provide helpful feedback.

        This method attempts to identify which courses and constraints are most
        likely causing the infeasibility.
        """
        logger.info("Analyzing infeasibility...")

        info = InfeasibilityInfo()

        courses_by_constraint_count: dict[str, int] = {}
        for course_code, course_vars in self.context.course_variables.items():
            constraint_involvement = 0

            constraint_involvement += len(course_vars.branches) * 2

            for section in course_vars.all_sections():
                constraint_involvement += len(section.instructors) * 3
                constraint_involvement += len(section.slot_vars)

            courses_by_constraint_count[course_code] = constraint_involvement

        sorted_courses = sorted(
            courses_by_constraint_count.items(), key=lambda x: x[1], reverse=True
        )
        info.problematic_courses = [code for code, _ in sorted_courses[:5]]

        branch_course_counts: dict[str, int] = {}
        for branch, courses in self.context.branch_courses.items():
            branch_course_counts[branch] = len(courses)

        overloaded_branches = [
            branch
            for branch, count in branch_course_counts.items()
            if count > 5
        ]

        if overloaded_branches:
            info.conflicting_constraints.append(
                f"Branches with many courses: {', '.join(overloaded_branches)}"
            )

        instructor_load: dict[str, int] = {}
        for instructor, sections in self.context.instructor_sections.items():
            instructor_load[instructor] = len(sections)

        overloaded_instructors = [
            instructor
            for instructor, load in instructor_load.items()
            if load > 4
        ]

        if overloaded_instructors:
            info.conflicting_constraints.append(
                f"Instructors with high load: {', '.join(overloaded_instructors)}"
            )

        info.suggestions = [
            "Try reducing the number of courses to schedule at once",
            "Check if any instructor is assigned to too many sections",
            "Verify that slot patterns have enough options for all course types",
            "Consider if some CDC courses for the same branch have conflicting patterns",
            "For DEL/HuEL courses, ensure there are enough pattern slots available",
        ]

        if info.problematic_courses:
            info.suggestions.append(
                f"Consider removing or rescheduling: {', '.join(info.problematic_courses[:3])}"
            )

        return info
