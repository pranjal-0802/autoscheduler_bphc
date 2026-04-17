"""
Objective function building for the timetable scheduler.
"""

from ortools.sat.python import cp_model

from src.solver.variables import SolverContext, SectionVariable
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ObjectiveBuilder:
    """Builds objective functions for the timetable scheduling problem."""

    WEIGHT_DISTRIBUTION = 100
    WEIGHT_NO_FIRST_LAST = 50
    WEIGHT_CONSECUTIVE_PENALTY = 200
    WEIGHT_GAP_PREFERENCE = 30
    WEIGHT_SECTION_OVERLAP = 80

    def __init__(self, context: SolverContext):
        """
        Initialize the objective builder.

        Args:
            context: The solver context containing model and variables.
        """
        self.ctx = context
        self.model = context.model

    def build_objective(self) -> None:
        """Build the complete objective function."""
        logger.info("Building objective function...")

        objective_terms: list[tuple[cp_model.IntVar, int]] = []

        objective_terms.extend(self._distribution_objective())
        objective_terms.extend(self._no_first_last_hour_objective())
        objective_terms.extend(self._minimize_consecutive_classes_objective())
        objective_terms.extend(self._section_overlap_objective())

        if objective_terms:
            self.model.Maximize(
                sum(coef * var for var, coef in objective_terms)
            )
            logger.info(f"Objective function built with {len(objective_terms)} terms")
        else:
            logger.warning("No objective terms created")

    def _distribution_objective(self) -> list[tuple[cp_model.IntVar, int]]:
        """
        Objective: Distribute classes evenly throughout the week.

        Returns:
            List of (variable, coefficient) tuples for the objective.
        """
        logger.debug("Building distribution objective...")
        terms = []

        for instructor, sections in self.ctx.instructor_sections.items():
            var_sections = [s for s in sections if isinstance(s, SectionVariable)]
            if not var_sections:
                continue

            for day_idx in range(6):
                day_slots = range(day_idx * 10, (day_idx + 1) * 10)

                classes_on_day = []
                for section in var_sections:
                    for slot_idx in day_slots:
                        if slot_idx in section.slot_vars:
                            classes_on_day.append(section.slot_vars[slot_idx])

                if len(classes_on_day) >= 2:
                    too_many = self.model.NewBoolVar(
                        f"too_many_{instructor}_day{day_idx}"
                    )
                    self.model.Add(sum(classes_on_day) > 4).OnlyEnforceIf(too_many)
                    self.model.Add(sum(classes_on_day) <= 4).OnlyEnforceIf(too_many.Not())
                    terms.append((too_many, -self.WEIGHT_DISTRIBUTION))

        return terms

    def _no_first_last_hour_objective(self) -> list[tuple[cp_model.IntVar, int]]:
        """
        Objective: Faculty preferably should not have both first and last hour.

        Returns:
            List of (variable, coefficient) tuples for the objective.
        """
        logger.debug("Building no first/last hour objective...")
        terms = []

        for instructor, sections in self.ctx.instructor_sections.items():
            var_sections = [s for s in sections if isinstance(s, SectionVariable)]
            if not var_sections:
                continue

            for day_idx in range(6):
                first_hour_idx = day_idx * 10
                last_hour_idx = day_idx * 10 + 9

                first_hour_vars = []
                last_hour_vars = []

                for section in var_sections:
                    if first_hour_idx in section.slot_vars:
                        first_hour_vars.append(section.slot_vars[first_hour_idx])
                    if last_hour_idx in section.slot_vars:
                        last_hour_vars.append(section.slot_vars[last_hour_idx])

                if first_hour_vars and last_hour_vars:
                    has_first = self.model.NewBoolVar(
                        f"has_first_{instructor}_day{day_idx}"
                    )
                    has_last = self.model.NewBoolVar(
                        f"has_last_{instructor}_day{day_idx}"
                    )
                    has_both = self.model.NewBoolVar(
                        f"has_both_{instructor}_day{day_idx}"
                    )

                    self.model.AddMaxEquality(has_first, first_hour_vars)
                    self.model.AddMaxEquality(has_last, last_hour_vars)
                    self.model.AddBoolAnd([has_first, has_last]).OnlyEnforceIf(has_both)
                    self.model.AddBoolOr(
                        [has_first.Not(), has_last.Not()]
                    ).OnlyEnforceIf(has_both.Not())

                    terms.append((has_both, -self.WEIGHT_NO_FIRST_LAST))

        return terms

    def _minimize_consecutive_classes_objective(
        self,
    ) -> list[tuple[cp_model.IntVar, int]]:
        """
        Objective: Minimize consecutive classes for faculty.

        Faculty preferably should not have 2 consecutive classes in any day.
        Prefer a gap of at least 2 hours, but 1 hour gap is acceptable.

        Returns:
            List of (variable, coefficient) tuples for the objective.
        """
        logger.debug("Building consecutive classes objective...")
        terms = []

        for instructor, sections in self.ctx.instructor_sections.items():
            var_sections = [s for s in sections if isinstance(s, SectionVariable)]
            if not var_sections:
                continue

            for day_idx in range(6):
                for hour in range(9):
                    slot_idx = day_idx * 10 + hour
                    next_slot_idx = slot_idx + 1

                    current_vars = []
                    next_vars = []

                    for section in var_sections:
                        if slot_idx in section.slot_vars:
                            is_end_of_section = True
                            if section.duration > 1:
                                start_slot = slot_idx - (section.duration - 1)
                                if start_slot in section.slot_vars:
                                    is_end_of_section = False
                            if is_end_of_section:
                                current_vars.append(section.slot_vars[slot_idx])

                        if next_slot_idx in section.slot_vars:
                            next_vars.append(section.slot_vars[next_slot_idx])

                    if current_vars and next_vars:
                        for curr_var in current_vars:
                            for next_var in next_vars:
                                both_consecutive = self.model.NewBoolVar(
                                    f"consecutive_{instructor}_slot{slot_idx}"
                                )
                                self.model.AddBoolAnd(
                                    [curr_var, next_var]
                                ).OnlyEnforceIf(both_consecutive)
                                self.model.AddBoolOr(
                                    [curr_var.Not(), next_var.Not()]
                                ).OnlyEnforceIf(both_consecutive.Not())

                                terms.append(
                                    (both_consecutive, -self.WEIGHT_CONSECUTIVE_PENALTY)
                                )

                for hour in range(8):
                    slot_idx = day_idx * 10 + hour
                    slot_plus_2 = slot_idx + 2

                    current_vars = []
                    later_vars = []

                    for section in var_sections:
                        if slot_idx in section.slot_vars:
                            current_vars.append(section.slot_vars[slot_idx])
                        if slot_plus_2 in section.slot_vars:
                            later_vars.append(section.slot_vars[slot_plus_2])

                    if current_vars and later_vars:
                        has_gap = self.model.NewBoolVar(
                            f"has_gap_{instructor}_slot{slot_idx}"
                        )

                        has_current = self.model.NewBoolVar(f"has_curr_{instructor}_{slot_idx}")
                        has_later = self.model.NewBoolVar(f"has_later_{instructor}_{slot_idx}")

                        self.model.AddMaxEquality(has_current, current_vars)
                        self.model.AddMaxEquality(has_later, later_vars)

                        next_slot = slot_idx + 1
                        next_vars = []
                        for section in var_sections:
                            if next_slot in section.slot_vars:
                                next_vars.append(section.slot_vars[next_slot])

                        if next_vars:
                            has_next = self.model.NewBoolVar(f"has_next_{instructor}_{slot_idx}")
                            self.model.AddMaxEquality(has_next, next_vars)
                            self.model.AddBoolAnd(
                                [has_current, has_next.Not(), has_later]
                            ).OnlyEnforceIf(has_gap)
                            terms.append((has_gap, self.WEIGHT_GAP_PREFERENCE))

        return terms

    def _section_overlap_objective(self) -> list[tuple[cp_model.IntVar, int]]:
        """
        Objective: Prefer sections of same type to overlap.

        Multiple lecture sections, tutorial sections, or practical sections of the
        same course should preferably overlap (unless faculty/rooms clash).

        Returns:
            List of (variable, coefficient) tuples for the objective.
        """
        logger.debug("Building section overlap objective...")
        terms = []

        for course_code, course_vars in self.ctx.course_variables.items():
            for section_type in ["lecture", "tutorial", "practical"]:
                sections = getattr(course_vars, f"{section_type}_sections")
                if len(sections) <= 1:
                    continue

                for slot_idx in range(60):
                    slot_vars = []
                    for section in sections:
                        if slot_idx in section.slot_vars:
                            slot_vars.append(section.slot_vars[slot_idx])

                    if len(slot_vars) >= 2:
                        all_overlap = self.model.NewBoolVar(
                            f"overlap_{course_code}_{section_type}_slot{slot_idx}"
                        )
                        self.model.AddBoolAnd(slot_vars).OnlyEnforceIf(all_overlap)
                        terms.append((all_overlap, self.WEIGHT_SECTION_OVERLAP))

        return terms
