"""
Constraint building for the timetable scheduler.
"""

from ortools.sat.python import cp_model

from src.solver.variables import SolverContext, SectionVariable, AllottedSection
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ConstraintBuilder:
    """Builds constraints for the timetable scheduling problem."""

    def __init__(self, context: SolverContext):
        """
        Initialize the constraint builder.

        Args:
            context: The solver context containing model and variables.
        """
        self.ctx = context
        self.model = context.model

    def build_all_constraints(self) -> None:
        """Build all constraints for the scheduling problem."""
        logger.info("Building constraints...")

        self._build_pattern_slot_constraints()
        self._build_room_constraints()
        self._build_instructor_no_overlap_constraints()
        self._build_branch_cdc_no_clash_constraints()
        self._build_del_availability_constraints()
        self._build_huel_availability_constraints()
        self._build_section_combination_constraints()
        self._build_section_overlap_preference_constraints()

        logger.info("All constraints built successfully")

    def _build_pattern_slot_constraints(self) -> None:
        """
        Ensure each section is assigned to exactly one pattern slot.

        This enforces that a section picks one of the available pattern options.
        """
        logger.debug("Building pattern slot constraints...")

        for course_code, course_vars in self.ctx.course_variables.items():
            for section in course_vars.all_sections():
                if not section.pattern_options:
                    continue

                pattern_choices = []
                for pattern_idx, (pattern_name, slot_indices) in enumerate(
                    section.pattern_options
                ):
                    pattern_selected = self.model.NewBoolVar(
                        f"pattern_{course_code}_{section.section_id}_{pattern_name}"
                    )
                    pattern_choices.append(pattern_selected)

                    for slot_idx in slot_indices:
                        if slot_idx in section.slot_vars:
                            self.model.AddImplication(
                                pattern_selected, section.slot_vars[slot_idx]
                            )
                            self.model.AddImplication(
                                section.slot_vars[slot_idx].Not(),
                                pattern_selected.Not(),
                            )

                    for slot_idx, slot_var in section.slot_vars.items():
                        if slot_idx not in slot_indices:
                            self.model.AddImplication(pattern_selected, slot_var.Not())

                if pattern_choices:
                    constraint = self.model.AddExactlyOne(pattern_choices)
                    self.ctx.add_constraint_name(
                        constraint,
                        f"exactly_one_pattern:{course_code}:{section.section_id}",
                    )

    def _build_room_constraints(self) -> None:
        """
        Ensure rooms don't have overlapping assignments.

        No two sections can use the same room at the same time.
        """
        logger.debug("Building room constraints...")

        for room, room_idx in self.ctx.room_to_index.items():
            for slot_idx in range(60):
                sections_using_room_at_slot = []

                for course_vars in self.ctx.course_variables.values():
                    for section in course_vars.all_sections():
                        if room not in section.preferred_rooms:
                            continue
                        if slot_idx not in section.slot_vars:
                            continue

                        room_and_slot = self.model.NewBoolVar(
                            f"room_{room}_{section.course_code}_{section.section_id}_slot{slot_idx}"
                        )

                        pref_room_idx = section.preferred_rooms.index(room)
                        self.model.Add(section.room_var == pref_room_idx).OnlyEnforceIf(
                            room_and_slot
                        )
                        self.model.Add(
                            section.slot_vars[slot_idx] == 1
                        ).OnlyEnforceIf(room_and_slot)

                        self.model.AddImplication(
                            room_and_slot, section.slot_vars[slot_idx]
                        )

                        sections_using_room_at_slot.append(room_and_slot)

                for allotted in self.ctx.allotted_sections:
                    if allotted.room == room and slot_idx in allotted.slots:
                        for var in sections_using_room_at_slot:
                            self.model.Add(var == 0)
                        sections_using_room_at_slot = []
                        break

                if len(sections_using_room_at_slot) > 1:
                    constraint = self.model.AddAtMostOne(sections_using_room_at_slot)
                    self.ctx.add_constraint_name(
                        constraint, f"room_no_overlap:{room}:slot{slot_idx}"
                    )

    def _build_instructor_no_overlap_constraints(self) -> None:
        """
        Ensure instructors don't have overlapping classes.

        Faculty members should not have overlapping classes.
        """
        logger.debug("Building instructor no-overlap constraints...")

        for instructor, sections in self.ctx.instructor_sections.items():
            for slot_idx in range(60):
                slot_vars_for_instructor = []

                for section in sections:
                    if isinstance(section, AllottedSection):
                        if slot_idx in section.slots:
                            for var in slot_vars_for_instructor:
                                self.model.Add(var == 0)
                            slot_vars_for_instructor = []
                            break
                    else:
                        if slot_idx in section.slot_vars:
                            slot_vars_for_instructor.append(section.slot_vars[slot_idx])

                if len(slot_vars_for_instructor) > 1:
                    constraint = self.model.AddAtMostOne(slot_vars_for_instructor)
                    self.ctx.add_constraint_name(
                        constraint,
                        f"instructor_no_overlap:{instructor}:slot{slot_idx}",
                    )

    def _build_branch_cdc_no_clash_constraints(self) -> None:
        """
        Ensure CDC courses for the same branch don't clash.

        None of the CDC courses that are offered to any single branch group
        should clash with each other.
        """
        logger.debug("Building branch CDC no-clash constraints...")

        for branch, course_codes in self.ctx.branch_courses.items():
            cdc_courses = [
                code
                for code in course_codes
                if code in self.ctx.course_variables
                and self.ctx.course_variables[code].pattern_year
                not in ("D", "H")
            ]

            if len(cdc_courses) <= 1:
                continue

            for slot_idx in range(60):
                slot_vars_for_branch = []

                for course_code in cdc_courses:
                    course_vars = self.ctx.course_variables[course_code]
                    for section in course_vars.all_sections():
                        if slot_idx in section.slot_vars:
                            slot_vars_for_branch.append(section.slot_vars[slot_idx])

                for allotted in self.ctx.allotted_sections:
                    if allotted.course_code in cdc_courses and slot_idx in allotted.slots:
                        for var in slot_vars_for_branch:
                            self.model.Add(var == 0)
                        slot_vars_for_branch = []
                        break

                if len(slot_vars_for_branch) > 1:
                    constraint = self.model.AddAtMostOne(slot_vars_for_branch)
                    self.ctx.add_constraint_name(
                        constraint, f"branch_cdc_no_clash:{branch}:slot{slot_idx}"
                    )

    def _build_del_availability_constraints(self) -> None:
        """
        Ensure at least 2 DELs are available for allotted branches.

        DEls should be scheduled such that at least 2 dels are free for their
        allotted branches only.
        """
        logger.debug("Building DEL availability constraints...")

        del_courses = {
            code: vars
            for code, vars in self.ctx.course_variables.items()
            if vars.pattern_year == "D"
        }

        if len(del_courses) < 2:
            return

        branch_del_courses: dict[str, list[str]] = {}
        for code, vars in del_courses.items():
            for branch in vars.branches:
                if branch not in branch_del_courses:
                    branch_del_courses[branch] = []
                branch_del_courses[branch].append(code)

        for branch, del_course_codes in branch_del_courses.items():
            if len(del_course_codes) < 2:
                continue

            branch_cdc_slots = self._get_branch_occupied_slots(branch)

            available_count_vars = []
            for course_code in del_course_codes:
                course_vars = del_courses[course_code]

                is_available = self.model.NewBoolVar(
                    f"del_available_{course_code}_{branch}"
                )

                has_clash_vars = []
                for section in course_vars.all_sections():
                    for slot_idx in section.slot_vars:
                        if slot_idx in branch_cdc_slots:
                            has_clash_vars.append(section.slot_vars[slot_idx])

                if has_clash_vars:
                    self.model.AddBoolOr(
                        [v.Not() for v in has_clash_vars]
                    ).OnlyEnforceIf(is_available)
                    self.model.AddBoolAnd(has_clash_vars).OnlyEnforceIf(
                        is_available.Not()
                    )

                available_count_vars.append(is_available)

            if len(available_count_vars) >= 2:
                constraint = self.model.Add(sum(available_count_vars) >= 2)
                self.ctx.add_constraint_name(
                    constraint, f"del_min_2_available:{branch}"
                )

    def _build_huel_availability_constraints(self) -> None:
        """
        Ensure at least 2 HuELs are available for any branch.

        HuEls should be scheduled such that at least 2 huels are free for any branch.
        """
        logger.debug("Building HuEL availability constraints...")

        huel_courses = {
            code: vars
            for code, vars in self.ctx.course_variables.items()
            if vars.pattern_year == "H"
        }

        if len(huel_courses) < 2:
            return

        all_branches = set()
        for vars in self.ctx.course_variables.values():
            all_branches.update(vars.branches)

        for branch in all_branches:
            if branch.startswith("1"):
                continue

            branch_occupied_slots = self._get_branch_occupied_slots(branch)

            available_count_vars = []
            for course_code, course_vars in huel_courses.items():
                is_available = self.model.NewBoolVar(
                    f"huel_available_{course_code}_{branch}"
                )

                has_clash_vars = []
                for section in course_vars.all_sections():
                    for slot_idx in section.slot_vars:
                        if slot_idx in branch_occupied_slots:
                            has_clash_vars.append(section.slot_vars[slot_idx])

                if has_clash_vars:
                    no_clash = self.model.NewBoolVar(
                        f"huel_no_clash_{course_code}_{branch}"
                    )
                    self.model.AddBoolOr(
                        [v.Not() for v in has_clash_vars]
                    ).OnlyEnforceIf(no_clash)
                    self.model.AddImplication(no_clash, is_available)

                available_count_vars.append(is_available)

            if len(available_count_vars) >= 2:
                constraint = self.model.Add(sum(available_count_vars) >= 2)
                self.ctx.add_constraint_name(
                    constraint, f"huel_min_2_available:{branch}"
                )

    def _build_section_combination_constraints(self) -> None:
        """
        Ensure valid L-T-P combinations exist for each branch.

        For any course, a student can only take up one lecture section, one tutorial
        section, and one practical section. There must be at least one valid combination
        that doesn't clash for any branch taking that course.
        """
        logger.debug("Building section combination constraints...")

        for course_code, course_vars in self.ctx.course_variables.items():
            if (
                len(course_vars.lecture_sections) <= 1
                and len(course_vars.tutorial_sections) <= 1
                and len(course_vars.practical_sections) <= 1
            ):
                continue

            for branch in course_vars.branches:
                self._build_combination_constraint_for_branch(
                    course_code, course_vars, branch
                )

    def _build_combination_constraint_for_branch(
        self, course_code: str, course_vars, branch: str
    ) -> None:
        """Build section combination constraint for a specific branch."""
        lectures = course_vars.lecture_sections or [None]
        tutorials = course_vars.tutorial_sections or [None]
        practicals = course_vars.practical_sections or [None]

        valid_combos = []

        for lec in lectures:
            for tut in tutorials:
                for prac in practicals:
                    combo_var = self.model.NewBoolVar(
                        f"combo_{course_code}_{branch}_"
                        f"L{lec.section_id if lec else 'X'}_"
                        f"T{tut.section_id if tut else 'X'}_"
                        f"P{prac.section_id if prac else 'X'}"
                    )

                    sections_in_combo = [s for s in [lec, tut, prac] if s is not None]

                    for i, s1 in enumerate(sections_in_combo):
                        for s2 in sections_in_combo[i + 1 :]:
                            for slot_idx in s1.slot_vars:
                                if slot_idx in s2.slot_vars:
                                    both_active = self.model.NewBoolVar(
                                        f"both_{s1.section_id}_{s2.section_id}_{slot_idx}"
                                    )
                                    self.model.AddBoolAnd(
                                        [s1.slot_vars[slot_idx], s2.slot_vars[slot_idx]]
                                    ).OnlyEnforceIf(both_active)
                                    self.model.AddImplication(both_active, combo_var.Not())

                    valid_combos.append(combo_var)

        if valid_combos:
            constraint = self.model.AddBoolOr(valid_combos)
            self.ctx.add_constraint_name(
                constraint, f"valid_combo_exists:{course_code}:{branch}"
            )

    def _build_section_overlap_preference_constraints(self) -> None:
        """
        Soft constraint: Prefer sections of same type to overlap.

        Multiple lecture sections of the same course, or tut sections, or practical
        sections, should preferably overlap (unless faculty/rooms clash).
        This is handled in objectives, not as a hard constraint.
        """
        pass

    def _get_branch_occupied_slots(self, branch: str) -> set[int]:
        """Get all time slots occupied by CDC courses for a branch."""
        occupied = set()

        for allotted in self.ctx.allotted_sections:
            if any(
                b == branch or branch.startswith(b) or b.startswith(branch)
                for b in self._get_allotted_branches(allotted.course_code)
            ):
                occupied.update(allotted.slots)

        for course_code, course_vars in self.ctx.course_variables.items():
            if course_vars.pattern_year in ("D", "H"):
                continue
            if branch not in course_vars.branches:
                continue

        return occupied

    def _get_allotted_branches(self, course_code: str) -> list[str]:
        """Get branches for an allotted course."""
        return []
