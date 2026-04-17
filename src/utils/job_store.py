"""
In-memory job storage for the scheduler.
"""

import threading
import uuid
from datetime import datetime
from typing import Optional

from src.models.job import Job, JobResult
from src.models.enums import JobStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)


class JobStore:
    """
    Thread-safe in-memory storage for scheduling jobs.

    This class provides a simple in-memory store for jobs. In a production
    environment, this would be replaced with a proper database or cache.
    """

    def __init__(self):
        """Initialize the job store."""
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()

    def create_job(self, request_data: Optional[dict] = None) -> Job:
        """
        Create a new job with a unique ID.

        Args:
            request_data: Optional request data to store with the job.

        Returns:
            The newly created Job instance.
        """
        job_id = str(uuid.uuid4())

        job = Job(
            id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.now(),
            request_data=request_data,
        )

        with self._lock:
            self._jobs[job_id] = job

        logger.info(f"Created job: {job_id}")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a job by its ID.

        Args:
            job_id: The job identifier.

        Returns:
            The Job if found, None otherwise.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def update_job_status(self, job_id: str, status: JobStatus) -> bool:
        """
        Update a job's status.

        Args:
            job_id: The job identifier.
            status: The new status.

        Returns:
            True if the job was found and updated, False otherwise.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False

            job.status = status

            if status == JobStatus.IN_PROGRESS:
                job.started_at = datetime.now()
            elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
                job.completed_at = datetime.now()

        logger.info(f"Updated job {job_id} status to {status.value}")
        return True

    def set_job_result(self, job_id: str, result: JobResult) -> bool:
        """
        Set the result for a job.

        Args:
            job_id: The job identifier.
            result: The job result.

        Returns:
            True if the job was found and updated, False otherwise.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False

            job.result = result

            if result.error:
                job.status = JobStatus.FAILED
            else:
                job.status = JobStatus.COMPLETED

            job.completed_at = datetime.now()

        logger.info(f"Set result for job {job_id}")
        return True

    def list_jobs(self, status: Optional[JobStatus] = None) -> list[Job]:
        """
        List all jobs, optionally filtered by status.

        Args:
            status: Optional status to filter by.

        Returns:
            List of matching jobs.
        """
        with self._lock:
            if status is None:
                return list(self._jobs.values())
            return [j for j in self._jobs.values() if j.status == status]

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job by ID.

        Args:
            job_id: The job identifier.

        Returns:
            True if the job was found and deleted, False otherwise.
        """
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                logger.info(f"Deleted job {job_id}")
                return True
            return False

    def clear_completed_jobs(self) -> int:
        """
        Remove all completed and failed jobs.

        Returns:
            Number of jobs removed.
        """
        with self._lock:
            to_remove = [
                job_id
                for job_id, job in self._jobs.items()
                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED)
            ]
            for job_id in to_remove:
                del self._jobs[job_id]

        logger.info(f"Cleared {len(to_remove)} completed/failed jobs")
        return len(to_remove)
