"""
Request validation logic for the scheduler.
"""

from dataclasses import dataclass, field
from typing import Any

from src.models.timeslot import TimeSlot, Day
from src.models.request import ScheduleRequestModel


@dataclass
class ValidationError:
    """
    Represents a validation error.

    Attributes:
        field: The field that failed validation.
        message: Description of the validation error.
        value: The invalid value (optional).
    """

    field: str
    message: str
    value: Any = None


@dataclass
class ValidationResult:
    """
    Result of validation.

    Attributes:
        is_valid: Whether the request is valid.
        errors: List of validation errors.
    """

    is_valid: bool = True
    errors: list[ValidationError] = field(default_factory=list)

    def add_error(self, field: str, message: str, value: Any = None) -> None:
        """Add a validation error."""
        self.errors.append(ValidationError(field=field, message=message, value=value))
        self.is_valid = False


class RequestValidator:
    """Validates scheduling request data."""

    VALID_DAYS = {d.value for d in Day}
    VALID_PATTERN_YEARS = {"1", "2", "3", "4", "D", "H"}
    VALID_SECTION_PREFIXES = {"L", "T", "P"}
    VALID_PATTERN_TYPE_PREFIXES = {"Lec", "Tut", "Pra"}

    def validate(self, request: ScheduleRequestModel) -> ValidationResult:
        """
        Validate a schedule request.

        Args:
            request: The schedule request to validate.

        Returns:
            ValidationResult with any errors found.
        """
        result = ValidationResult()

        self._validate_patterns(request.patterns, result)
        self._validate_allotted_courses(request.allotted, request.patterns, result)
        self._validate_courses_to_schedule(request.toschedule, request.patterns, result)

        return result

    def _validate_patterns(
        self, patterns: dict[str, dict[str, list[str]]], result: ValidationResult
    ) -> None:
        """Validate slot patterns configuration."""
        if not patterns:
            result.add_error("patterns", "Patterns configuration is required")
            return

        for pattern_year, pattern_types in patterns.items():
            if pattern_year not in self.VALID_PATTERN_YEARS:
                result.add_error(
                    f"patterns.{pattern_year}",
                    f"Invalid pattern year. Must be one of {self.VALID_PATTERN_YEARS}",
                    pattern_year,
                )
                continue

            for pattern_type, slots in pattern_types.items():
                if not any(pattern_type.startswith(p) for p in self.VALID_PATTERN_TYPE_PREFIXES):
                    result.add_error(
                        f"patterns.{pattern_year}.{pattern_type}",
                        f"Invalid pattern type prefix. Must start with one of {self.VALID_PATTERN_TYPE_PREFIXES}",
                        pattern_type,
                    )

                for slot in slots:
                    if not self._is_valid_timeslot(slot):
                        result.add_error(
                            f"patterns.{pattern_year}.{pattern_type}",
                            f"Invalid time slot format: {slot}",
                            slot,
                        )

    def _validate_allotted_courses(
        self,
        courses: list[Any],
        patterns: dict[str, dict[str, list[str]]],
        result: ValidationResult,
    ) -> None:
        """Validate already allotted courses."""
        seen_codes = set()

        for i, course in enumerate(courses):
            course_prefix = f"allotted[{i}]"

            if not course.code:
                result.add_error(f"{course_prefix}.code", "Course code is required")
            elif course.code in seen_codes:
                result.add_error(
                    f"{course_prefix}.code",
                    f"Duplicate course code: {course.code}",
                    course.code,
                )
            seen_codes.add(course.code)

            if not course.branches:
                result.add_error(
                    f"{course_prefix}.branches", "At least one branch is required"
                )
            else:
                for branch in course.branches:
                    if not self._is_valid_branch(branch):
                        result.add_error(
                            f"{course_prefix}.branches",
                            f"Invalid branch format: {branch}",
                            branch,
                        )

            if course.patternYear not in self.VALID_PATTERN_YEARS:
                result.add_error(
                    f"{course_prefix}.patternYear",
                    f"Invalid pattern year. Must be one of {self.VALID_PATTERN_YEARS}",
                    course.patternYear,
                )

            self._validate_class_specs(course, course_prefix, result)
            self._validate_allotment(course, course_prefix, result)

    def _validate_courses_to_schedule(
        self,
        courses: list[Any],
        patterns: dict[str, dict[str, list[str]]],
        result: ValidationResult,
    ) -> None:
        """Validate courses to be scheduled."""
        seen_codes = set()

        for i, course in enumerate(courses):
            course_prefix = f"toschedule[{i}]"

            if not course.code:
                result.add_error(f"{course_prefix}.code", "Course code is required")
            elif course.code in seen_codes:
                result.add_error(
                    f"{course_prefix}.code",
                    f"Duplicate course code: {course.code}",
                    course.code,
                )
            seen_codes.add(course.code)

            if not course.branches:
                result.add_error(
                    f"{course_prefix}.branches", "At least one branch is required"
                )
            else:
                for branch in course.branches:
                    if not self._is_valid_branch(branch):
                        result.add_error(
                            f"{course_prefix}.branches",
                            f"Invalid branch format: {branch}",
                            branch,
                        )

            if course.patternYear not in self.VALID_PATTERN_YEARS:
                result.add_error(
                    f"{course_prefix}.patternYear",
                    f"Invalid pattern year. Must be one of {self.VALID_PATTERN_YEARS}",
                    course.patternYear,
                )
            elif course.patternYear not in patterns:
                result.add_error(
                    f"{course_prefix}.patternYear",
                    f"Pattern year '{course.patternYear}' not defined in patterns",
                    course.patternYear,
                )

            self._validate_class_specs(course, course_prefix, result)

            if not course.L and not course.T and not course.P:
                result.add_error(
                    course_prefix,
                    "At least one class type (L, T, or P) must be specified",
                )

    def _validate_class_specs(
        self, course: Any, prefix: str, result: ValidationResult
    ) -> None:
        """Validate class specifications for a course."""
        for class_type in ["L", "T", "P"]:
            spec = getattr(course, class_type, None)
            if spec is None:
                continue

            spec_prefix = f"{prefix}.{class_type}"

            if spec.duration < 1:
                result.add_error(
                    f"{spec_prefix}.duration",
                    "Duration must be at least 1",
                    spec.duration,
                )

            if spec.perweek < 0:
                result.add_error(
                    f"{spec_prefix}.perweek",
                    "Per week sessions must be non-negative",
                    spec.perweek,
                )

            if spec.sections:
                seen_section_ids = set()
                for j, section in enumerate(spec.sections):
                    section_prefix = f"{spec_prefix}.sections[{j}]"

                    if not section.id:
                        result.add_error(
                            f"{section_prefix}.id", "Section ID is required"
                        )
                    elif not section.id.startswith(class_type):
                        result.add_error(
                            f"{section_prefix}.id",
                            f"Section ID must start with '{class_type}'",
                            section.id,
                        )

                    if section.id in seen_section_ids:
                        result.add_error(
                            f"{section_prefix}.id",
                            f"Duplicate section ID: {section.id}",
                            section.id,
                        )
                    seen_section_ids.add(section.id)

    def _validate_allotment(
        self, course: Any, prefix: str, result: ValidationResult
    ) -> None:
        """Validate allotment for an already scheduled course."""
        if not hasattr(course, "allotment") or not course.allotment:
            result.add_error(
                f"{prefix}.allotment", "Allotment is required for allotted courses"
            )
            return

        for section_id, slots in course.allotment.items():
            if not any(section_id.startswith(p) for p in self.VALID_SECTION_PREFIXES):
                result.add_error(
                    f"{prefix}.allotment.{section_id}",
                    f"Invalid section ID prefix. Must start with one of {self.VALID_SECTION_PREFIXES}",
                    section_id,
                )

            for slot in slots:
                if not self._is_valid_timeslot(slot):
                    result.add_error(
                        f"{prefix}.allotment.{section_id}",
                        f"Invalid time slot format: {slot}",
                        slot,
                    )

    def _is_valid_timeslot(self, slot: str) -> bool:
        """Check if a time slot string is valid."""
        try:
            TimeSlot.from_string(slot)
            return True
        except ValueError:
            return False

    def _is_valid_branch(self, branch: str) -> bool:
        """
        Check if a branch string is valid.

        Valid formats: '1A', '2B3', '3A7', '3B5A7', etc.
        First character must be a digit (year), followed by alternating
        letter (group) and optional digit (sub-group) combinations.
        """
        if not branch or len(branch) < 2:
            return False

        if not branch[0].isdigit():
            return False

        year = int(branch[0])
        if not 1 <= year <= 4:
            return False

        rest = branch[1:]
        i = 0
        while i < len(rest):
            if not rest[i].isalpha():
                return False
            i += 1
            while i < len(rest) and rest[i].isdigit():
                i += 1

        return True
