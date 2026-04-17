# Auto Timetable Scheduler

An automatic timetable scheduler using Google's OR-Tools CP-SAT solver for optimal timetable generation. The service is provided as an API using FastAPI for the main Timetable Scheduler website to interact with.

## Table of Contents

- [Overview](#overview)
- [Setup](#setup)
  - [Using uv (Recommended)](#using-uv-recommended)
  - [Using pip](#using-pip)
  - [Using Docker](#using-docker)
- [Running the Server](#running-the-server)
- [API Endpoints](#api-endpoints)
- [Data Formats](#data-formats)
- [Constraints and Scoring](#constraints-and-scoring)
- [Infeasibility Analysis](#infeasibility-analysis)
- [Project Structure](#project-structure)

## Overview

The Timetable Scheduler server accepts scheduling jobs with course details and constraints, spawns a separate process to formulate the problem for Google's OR-Tools CP-SAT solver, and finds the optimal (or at least feasible) timetable based on multiple constraints and scoring factors.

### Key Features

- **Constraint-based scheduling**: Handles CDC, DEL, and HuEL course types with different constraints
- **Faculty conflict detection**: Prevents instructor overlaps
- **Room management**: Assigns rooms from preferred lists without conflicts
- **Branch conflict avoidance**: Ensures students can take all required courses
- **Optimization objectives**: Distributes classes evenly and minimizes consecutive teaching hours
- **Infeasibility analysis**: Provides insights when no solution exists

## Setup

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver.

1. **Install uv** (if not already installed):
   ```bash
   # On macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # On Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd autoscheduler
   ```

3. **Create virtual environment and install dependencies**:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

4. **For development dependencies**:
   ```bash
   uv pip install -e ".[dev]"
   ```

### Using pip

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd autoscheduler
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -e .
   ```

### Using Docker

1. **Build the image**:
   ```bash
   docker build -t autoscheduler .
   ```

2. **Run with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

## Running the Server

### Development Mode

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at `http://localhost:8000`.

### API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### 1. Submit a Scheduling Job

**POST** `/submit`

Submit a new scheduling job with courses and patterns.

**Request Body:**
```json
{
    "allotted": [...],
    "toschedule": [...],
    "patterns": {...}
}
```

**Response (202 Accepted):**
```json
{
    "job_id": "some-unique-job-id"
}
```

### 2. Check Job Status

**GET** `/status/{job_id}`

Check the status of a scheduling job.

**Response:**
```json
{
    "status": "pending"  // or "in_progress", "completed", "failed"
}
```

### 3. Get Job Result

**GET** `/result/{job_id}`

Get the result of a completed job.

**Response (Success):**
```json
{
    "timetable": {
        "CS F345": {
            "L1": {
                "room": "F102",
                "slots": ["Mo1", "We1", "Fr1"]
            }
        }
    },
    "solve_time_seconds": 12.5
}
```

**Response (Failure with Infeasibility Analysis):**
```json
{
    "error": "No feasible solution exists for the given constraints",
    "infeasibility_info": {
        "problematic_courses": ["CS F342", "CS F345"],
        "conflicting_constraints": ["Branches with many courses: 2A5"],
        "suggestions": [
            "Try reducing the number of courses to schedule at once",
            "Check if any instructor is assigned to too many sections"
        ]
    },
    "solve_time_seconds": 300.0
}
```

### 4. Additional Endpoints

- **GET** `/health` - Health check
- **GET** `/jobs` - List all jobs
- **DELETE** `/jobs/{job_id}` - Delete a job
- **POST** `/jobs/clear` - Clear completed/failed jobs

## Data Formats

### Time Slots

Format: `<Day(2)><Hour>` where:
- Day: `Mo`, `Tu`, `We`, `Th`, `Fr`, `Sa`
- Hour: 1-10

Examples: `Mo1`, `Th8`, `Fr10`

### Slot Patterns

Pattern types identify slot groupings in the master timetable:
- `Lec1`, `Lec2`, ... - Lecture patterns
- `Tut1`, `Tut2`, ... - Tutorial patterns
- `Pra1`, `Pra2`, ... - Practical patterns

### Section IDs

- `L1`, `L2`, ... - Lecture sections
- `T1`, `T2`, ... - Tutorial sections
- `P1`, `P2`, ... - Practical sections

### Branch Groups

Format: `<Year><Group>[<SubGroup>]...`

Examples:
- `1A`, `1B` - Year 1, Group A/B
- `2A5` - Year 2, Group A, Branch 5
- `3B5A7` - Year 3, Group B5 and A7

### Complete Request Example

```json
{
    "allotted": [
        {
            "code": "CS F342",
            "branches": ["3A5", "3B5"],
            "patternYear": "3",
            "L": {
                "duration": 1,
                "perweek": 3,
                "sections": [
                    {"id": "L1", "instructors": ["Dr. Smith"], "preferredRooms": ["F102", "F105"]}
                ]
            },
            "T": {
                "duration": 1,
                "perweek": 2
            },
            "allotment": {
                "L1": ["Mo1", "We1", "Fr1"],
                "T1": ["Tu2", "Th2"]
            }
        }
    ],
    "toschedule": [
        {
            "code": "CS F345",
            "branches": ["3A5", "3B5", "3A7"],
            "patternYear": "3",
            "L": {
                "duration": 1,
                "perweek": 3,
                "sections": [
                    {"id": "L1", "instructors": ["Dr. Jones"], "preferredRooms": ["F105"]},
                    {"id": "L2", "instructors": ["Dr. Brown"], "preferredRooms": ["F102"]}
                ]
            },
            "T": {
                "duration": 1,
                "perweek": 2,
                "sections": [
                    {"id": "T1", "instructors": ["TA1"], "preferredRooms": ["G101"]}
                ]
            }
        }
    ],
    "patterns": {
        "3": {
            "Lec1": ["Mo3", "We3", "Fr3"],
            "Lec2": ["Tu4", "Th4", "Fr4"],
            "Tut1": ["Mo5", "We5"],
            "Tut2": ["Tu5", "Th5"]
        },
        "D": {
            "Lec1": ["Tu7", "Th7"],
            "Lec2": ["We8", "Fr8"]
        },
        "H": {
            "Lec1": ["Mo9", "We9"],
            "Lec2": ["Tu9", "Th9"]
        }
    }
}
```

## Constraints and Scoring

### Hard Constraints

1. **CDC No-Clash**: CDC courses for the same branch cannot have overlapping time slots
2. **DEL Availability**: At least 2 DELs must be free (no clash) for their allotted branches
3. **HuEL Availability**: At least 2 HuELs must be free for any non-first-year branch
4. **Faculty No-Overlap**: Instructors cannot teach multiple classes at the same time
5. **Room No-Conflict**: A room can only host one class at a time
6. **Valid Section Combinations**: For each course, at least one L-T-P combination must be clash-free

### Soft Constraints (Optimization Objectives)

1. **Even Distribution**: Classes should be distributed evenly throughout the week
2. **No First-Last Hour**: Faculty preferably shouldn't have classes in both hour 1 and hour 10 of the same day
3. **Minimize Consecutive Classes**: Faculty should have gaps between classes (preferably 2+ hours)
4. **Section Overlap Preference**: Multiple sections of the same type should overlap when possible (for room/instructor efficiency)

## Infeasibility Analysis

When the solver cannot find a feasible solution, it provides analysis including:

- **Problematic Courses**: Courses most likely causing conflicts (based on constraint involvement)
- **Conflicting Constraints**: Identified sources of conflicts (e.g., overloaded branches or instructors)
- **Suggestions**: Actionable recommendations to resolve the infeasibility

This helps users identify which courses or patterns to modify to make the problem solvable.

### Note on CP-SAT Infeasibility Analysis

The CP-SAT solver in OR-Tools doesn't provide built-in detailed infeasibility certificates like some MIP solvers do. Our implementation uses heuristic analysis to identify:

1. Courses with the most constraint involvement
2. Branches with too many scheduled courses
3. Instructors with excessive teaching loads

For more precise infeasibility analysis, one would need to implement incremental constraint relaxation or use the solver's assumption-based features, which is computationally expensive and not suitable for real-time API responses.

## Project Structure

```
autoscheduler/
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── models/                 # Data models
│   │   ├── __init__.py
│   │   ├── enums.py           # Enumerations
│   │   ├── timeslot.py        # TimeSlot class
│   │   ├── course.py          # Course-related models
│   │   ├── job.py             # Job and result models
│   │   └── request.py         # API request models
│   ├── validation/            # Request validation
│   │   ├── __init__.py
│   │   └── validators.py      # Validation logic
│   ├── solver/                # CP-SAT solver
│   │   ├── __init__.py
│   │   ├── scheduler.py       # Main scheduler
│   │   ├── variables.py       # Solver variables
│   │   ├── constraints.py     # Constraint builder
│   │   └── objectives.py      # Objective builder
│   ├── response/              # Response formatting
│   │   ├── __init__.py
│   │   └── formatter.py       # Response formatter
│   └── utils/                 # Utilities
│       ├── __init__.py
│       ├── logging.py         # Logging setup
│       └── job_store.py       # Job storage
├── logs/                      # Log files (date-stamped)
├── tests/                     # Test files
├── pyproject.toml            # Project configuration
├── requirements.txt          # Dependencies
├── Dockerfile               # Docker build file
├── docker-compose.yml       # Docker Compose config
├── .env.example            # Environment variables template
├── .gitignore
└── README.md
```

## Logging

Logs are written to the `logs/` directory with date-stamped filenames (e.g., `2026-02-02.log`). The logging configuration can be adjusted via environment variables:

- `LOG_LEVEL`: Set to `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`

## Environment Variables

Copy `.env.example` to `.env` and configure:

```env
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
SOLVER_TIME_LIMIT_SECONDS=300
SOLVER_NUM_WORKERS=0  # 0 = auto-detect
```

## License

MIT License
