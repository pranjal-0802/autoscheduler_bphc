# Auto Timetable Scheduler
This project aims to set up an automatic timetable scheduler using Google's OR-Tools, for the most optimal timetable generation based on various constraints. The service will be served as an (unprotected) API using FastAPI for the main Timetable Scheduler website to interact with it, submitting jobs as required. The project is also containerized using Docker.

## Overview
The Timetable Scheduler server can submit a job to this system with all the courses and their details, which will spawn a separate process that will formulate the problem for Google's OR-Tools and use its CP-SAT solver to find the optimal (or at least a feasible) timetable, using multiple constraints as well as factors that score certain arrangements better than the others

## Before you begin reading
1. The timeslot should be formatted as '<Double character day><Hour>', for instance, 'Mo1', 'Th8', etc.
2. The Master timetable slots will be referred to as slot pattern, and the slot type can be identified in the format 'Lec1', 'Tut6', 'Pra4', etc. Note how that is differentiated from the course sections which will still be referred to as 'L1', 'T4', 'P3', etc.
3. Branch groups will be mentioned as a list as follows (by example): '1A', '1B' (Year 1, group A/B), '2A7', '2B3', '3A7', '3B5A7' (make sure to list out all combinations of B-A- branches that actually have that course as a CDC, since sometimes you can have cases where, say, B4A7 will not have the course, but other B groups will)

## Endpoints
1. `POST /submit`: Expects a JSON payload in the following format:
```json
{
  
}
```