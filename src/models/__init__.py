"""
Models package containing all data structures and types for the scheduler.
"""

from src.models.enums import JobStatus, ClassType, CourseType
from src.models.course import (
    Section,
    ClassSpec,
    CourseAllotment,
    AllottedCourse,
    CourseToSchedule,
)
from src.models.job import Job, JobResult, ScheduleResult, SectionAllotment
from src.models.request import ScheduleRequest, SlotPatterns
from src.models.timeslot import TimeSlot, Day

__all__ = [
    "JobStatus",
    "ClassType",
    "CourseType",
    "Section",
    "ClassSpec",
    "CourseAllotment",
    "AllottedCourse",
    "CourseToSchedule",
    "Job",
    "JobResult",
    "ScheduleResult",
    "SectionAllotment",
    "ScheduleRequest",
    "SlotPatterns",
    "TimeSlot",
    "Day",
]
