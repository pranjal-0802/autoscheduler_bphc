"""
Auto Timetable Scheduler API Server.

This module provides the FastAPI application for the timetable scheduling service.
"""

import concurrent.futures
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from src.models.request import ScheduleRequestModel
from src.models.enums import JobStatus
from src.validation import RequestValidator
from src.solver import TimetableScheduler, SchedulerConfig
from src.response import ResponseFormatter
from src.utils import setup_logging, get_logger, JobStore

logger = get_logger(__name__)

job_store = JobStore()

executor = concurrent.futures.ProcessPoolExecutor(max_workers=2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Sets up logging and cleans up resources on shutdown.
    """
    setup_logging(logs_dir="logs")
    logger.info("Auto Timetable Scheduler starting up...")
    yield
    logger.info("Auto Timetable Scheduler shutting down...")
    executor.shutdown(wait=False)


app = FastAPI(
    title="Auto Timetable Scheduler",
    description="An automatic timetable scheduler using Google OR-Tools CP-SAT solver",
    version="0.1.0",
    lifespan=lifespan,
)


def run_scheduler(request_dict: dict[str, Any], job_id: str) -> dict[str, Any]:
    """
    Run the scheduler in a separate process.

    Args:
        request_dict: The schedule request as a dictionary.
        job_id: The job identifier for logging.

    Returns:
        The job result as a dictionary.
    """
    setup_logging(logs_dir="logs")
    process_logger = get_logger(f"scheduler.{job_id}")
    process_logger.info(f"Starting scheduler for job {job_id}")

    try:
        request = ScheduleRequestModel(**request_dict)

        config = SchedulerConfig(
            time_limit_seconds=300.0,
            log_search_progress=True,
        )
        scheduler = TimetableScheduler(config=config)
        result = scheduler.solve(request)

        result_dict = {
            "schedule": None,
            "error": result.error,
            "infeasibility_info": None,
            "solve_time_seconds": result.solve_time_seconds,
            "solver_stats": result.solver_stats,
        }

        if result.schedule is not None:
            result_dict["schedule"] = {
                "timetable": {
                    course: {
                        section: {"room": allot.room, "slots": allot.slots}
                        for section, allot in sections.items()
                    }
                    for course, sections in result.schedule.timetable.items()
                }
            }

        if result.infeasibility_info is not None:
            result_dict["infeasibility_info"] = {
                "problematic_courses": result.infeasibility_info.problematic_courses,
                "conflicting_constraints": result.infeasibility_info.conflicting_constraints,
                "suggestions": result.infeasibility_info.suggestions,
            }

        process_logger.info(f"Scheduler completed for job {job_id}")
        return result_dict

    except Exception as e:
        process_logger.exception(f"Scheduler failed for job {job_id}")
        return {
            "schedule": None,
            "error": str(e),
            "infeasibility_info": None,
            "solve_time_seconds": None,
            "solver_stats": {"exception": str(e)},
        }


async def process_job(job_id: str, request_dict: dict[str, Any]) -> None:
    """
    Process a scheduling job asynchronously.

    Args:
        job_id: The job identifier.
        request_dict: The schedule request as a dictionary.
    """
    logger.info(f"Processing job {job_id}")

    job_store.update_job_status(job_id, JobStatus.IN_PROGRESS)

    try:
        loop = __import__("asyncio").get_event_loop()
        result_dict = await loop.run_in_executor(
            executor, run_scheduler, request_dict, job_id
        )

        from src.models.job import JobResult, ScheduleResult, SectionAllotment, InfeasibilityInfo

        schedule = None
        if result_dict.get("schedule") is not None:
            timetable_data = result_dict["schedule"]["timetable"]
            schedule = ScheduleResult(
                timetable={
                    course: {
                        section: SectionAllotment(
                            room=allot["room"], slots=allot["slots"]
                        )
                        for section, allot in sections.items()
                    }
                    for course, sections in timetable_data.items()
                }
            )

        infeasibility_info = None
        if result_dict.get("infeasibility_info") is not None:
            info_data = result_dict["infeasibility_info"]
            infeasibility_info = InfeasibilityInfo(
                problematic_courses=info_data.get("problematic_courses", []),
                conflicting_constraints=info_data.get("conflicting_constraints", []),
                suggestions=info_data.get("suggestions", []),
            )

        job_result = JobResult(
            schedule=schedule,
            error=result_dict.get("error"),
            infeasibility_info=infeasibility_info,
            solve_time_seconds=result_dict.get("solve_time_seconds"),
            solver_stats=result_dict.get("solver_stats", {}),
        )

        job_store.set_job_result(job_id, job_result)
        logger.info(f"Job {job_id} completed")

    except Exception as e:
        logger.exception(f"Error processing job {job_id}")
        from src.models.job import JobResult

        job_result = JobResult(
            error=f"Processing error: {str(e)}",
            solver_stats={"exception": str(e)},
        )
        job_store.set_job_result(job_id, job_result)


@app.post("/submit")
async def submit_job(
    request: ScheduleRequestModel, background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Submit a new scheduling job.

    Args:
        request: The schedule request containing courses and patterns.
        background_tasks: FastAPI background tasks handler.

    Returns:
        JSON response with the job ID.
    """
    logger.info("Received scheduling request")

    validator = RequestValidator()
    validation_result = validator.validate(request)

    if not validation_result.is_valid:
        logger.warning(f"Validation failed: {len(validation_result.errors)} errors")
        return JSONResponse(
            status_code=400,
            content=ResponseFormatter.format_validation_errors(validation_result.errors),
        )

    request_dict = request.model_dump()

    job = job_store.create_job(request_data=request_dict)

    background_tasks.add_task(process_job, job.id, request_dict)

    return JSONResponse(
        status_code=202,
        content=ResponseFormatter.format_submit_response(job.id),
    )


@app.get("/status/{job_id}")
async def get_job_status(job_id: str) -> JSONResponse:
    """
    Get the status of a scheduling job.

    Args:
        job_id: The unique job identifier.

    Returns:
        JSON response with the job status.

    Raises:
        HTTPException: If the job is not found.
    """
    job = job_store.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JSONResponse(content=ResponseFormatter.format_status_response(job))


@app.get("/result/{job_id}")
async def get_job_result(job_id: str) -> JSONResponse:
    """
    Get the result of a completed scheduling job.

    Args:
        job_id: The unique job identifier.

    Returns:
        JSON response with the scheduling result.

    Raises:
        HTTPException: If the job is not found or not complete.
    """
    job = job_store.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job.status == JobStatus.PENDING:
        raise HTTPException(
            status_code=400, detail="Job is still pending, not yet started"
        )

    if job.status == JobStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Job is still in progress")

    return JSONResponse(content=ResponseFormatter.format_result_response(job))


@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Dictionary with health status.
    """
    return {"status": "healthy"}


@app.get("/jobs")
async def list_jobs() -> JSONResponse:
    """
    List all jobs with their statuses.

    Returns:
        JSON response with list of jobs.
    """
    jobs = job_store.list_jobs()

    return JSONResponse(
        content={
            "jobs": [
                {
                    "id": job.id,
                    "status": job.status.value,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "completed_at": (
                        job.completed_at.isoformat() if job.completed_at else None
                    ),
                }
                for job in jobs
            ]
        }
    )


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> JSONResponse:
    """
    Delete a job.

    Args:
        job_id: The unique job identifier.

    Returns:
        JSON response confirming deletion.

    Raises:
        HTTPException: If the job is not found.
    """
    if not job_store.delete_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JSONResponse(content={"deleted": job_id})


@app.post("/jobs/clear")
async def clear_completed_jobs() -> JSONResponse:
    """
    Clear all completed and failed jobs.

    Returns:
        JSON response with the number of jobs cleared.
    """
    count = job_store.clear_completed_jobs()

    return JSONResponse(content={"cleared": count})
