"""
Time slot representations for the scheduler.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Self


class Day(Enum):
    """Days of the week."""

    MONDAY = "Mo"
    TUESDAY = "Tu"
    WEDNESDAY = "We"
    THURSDAY = "Th"
    FRIDAY = "Fr"
    SATURDAY = "Sa"

    @classmethod
    def from_code(cls, code: str) -> "Day":
        """
        Create a Day from its two-letter code.

        Args:
            code: Two-letter day code (e.g., 'Mo', 'Tu').

        Returns:
            The corresponding Day enum value.

        Raises:
            ValueError: If the code is not a valid day code.
        """
        for day in cls:
            if day.value == code:
                return day
        raise ValueError(f"Invalid day code: {code}")


@dataclass(frozen=True)
class TimeSlot:
    """
    Represents a single time slot in the timetable.

    A time slot is identified by its day and hour. For example, 'Mo1' represents
    Monday, 1st hour. Hours are 1-indexed.
    """

    day: Day
    hour: int

    def __post_init__(self) -> None:
        """Validate the hour is within valid range (1-10)."""
        if not 1 <= self.hour <= 10:
            raise ValueError(f"Hour must be between 1 and 10, got {self.hour}")

    @classmethod
    def from_string(cls, slot_str: str) -> Self:
        """
        Parse a time slot from string format.

        Args:
            slot_str: Time slot string in format '<Day(2)><Hour>' (e.g., 'Mo1', 'Th8').

        Returns:
            A TimeSlot instance.

        Raises:
            ValueError: If the string format is invalid.
        """
        if len(slot_str) < 3:
            raise ValueError(f"Invalid time slot format: {slot_str}")

        day_code = slot_str[:2]
        try:
            hour = int(slot_str[2:])
        except ValueError:
            raise ValueError(f"Invalid hour in time slot: {slot_str}")

        return cls(day=Day.from_code(day_code), hour=hour)

    def __str__(self) -> str:
        """Return string representation in standard format."""
        return f"{self.day.value}{self.hour}"

    def __repr__(self) -> str:
        """Return detailed string representation."""
        return f"TimeSlot({self.day.value}{self.hour})"

    def to_index(self) -> int:
        """
        Convert time slot to a unique integer index.

        Returns:
            Integer index where Monday hour 1 = 0, Monday hour 2 = 1, ..., Saturday hour 10 = 59.
        """
        day_index = list(Day).index(self.day)
        return day_index * 10 + (self.hour - 1)

    @classmethod
    def from_index(cls, index: int) -> Self:
        """
        Create a TimeSlot from its integer index.

        Args:
            index: Integer index (0-59).

        Returns:
            The corresponding TimeSlot.
        """
        day_index = index // 10
        hour = (index % 10) + 1
        return cls(day=list(Day)[day_index], hour=hour)
