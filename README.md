# Adaptive Technical Viva & Oral Screener

An AI-powered technical viva and oral examination system for Computer Science subjects: **Operating Systems (OS)**, **Database Management Systems (DBMS)**, and **Computer Networks (CN)**. The platform assesses conceptual understanding, evaluates student answers, identifies conceptual gaps, and adaptively tailors follow-up questions.

---

## 🛠 Technology Stack

- **Language:** Python 3.10+ (tested on Python 3.13)
- **Web Framework:** [FastAPI](https://fastapi.tiangolo.com/) (modern, high-performance async framework)
- **ASGI Server:** [Uvicorn](https://www.uvicorn.org/) (lightning-fast ASGI server)
- **Configuration & Validation:** [Pydantic v2](https://docs.pydantic.dev/) & [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **Database:** [MongoDB](https://www.mongodb.com/) using [PyMongo](https://pymongo.readthedocs.io/)'s official asynchronous API (`AsyncMongoClient`)
- **Testing:** [pytest](https://docs.pytest.org/) & [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- **HTTP Client:** [HTTPX](https://www.python-httpx.org/) (async test client)

---

## 📂 Project Architecture

```
Adaptive-Technical-Viva-Oral-Screener/
├── .env.example              # Template for environment variables
├── .gitignore                # Git exclusions (venv, secrets, cache)
├── pytest.ini                # Pytest configuration and path settings
├── requirements.txt          # Python project dependencies
├── README.md                 # Project documentation and setup guide
├── app/
│   ├── __init__.py           # Application package marker
│   ├── main.py               # FastAPI application factory, middleware, and lifecycle
│   ├── api/
│   │   ├── __init__.py       # API package marker
│   │   ├── api_v1/
│   │   │   ├── __init__.py   # API v1 package marker
│   │   │   └── api.py        # API v1 centralized route registry
│   │   └── endpoints/
│   │       ├── __init__.py   # Endpoints package marker
│   │       └── health.py     # /api/v1/health status endpoint handler
│   ├── core/
│   │   ├── __init__.py       # Core package marker
│   │   ├── config.py         # Pydantic BaseSettings environment loader
│   │   └── logging.py        # Centralized structured logging setup
│   ├── db/
│   │   ├── __init__.py       # Database package marker
│   │   └── mongodb.py        # PyMongo AsyncMongoClient connection manager
│   ├── models/
│   │   └── __init__.py       # Database models package marker
│   └── schemas/
│       ├── __init__.py       # Schemas package marker
│       └── health.py         # Pydantic request/response schemas for health check
├── backend/
│   └── main.py               # Compatibility bridge importing app.main:app
└── tests/
    ├── __init__.py           # Test suite package marker
    ├── conftest.py           # Pytest test fixtures (async client)
    ├── test_api.py           # Configuration and error-handling tests
    └── test_health.py        # Health-check and root route tests
```

---

## 📋 Major Files & Their Purpose

| File | Purpose |
| :--- | :--- |
| `app/main.py` | Instantiates FastAPI, initializes logging, manages startup/shutdown lifecycle (MongoDB connect/disconnect), configures CORS, handles global exceptions, and mounts API routers. |
| `app/core/config.py` | Defines the `Settings` class using Pydantic Settings. Reads configuration from `.env` with type validation and sane defaults. |
| `app/core/logging.py` | Configures structured logging with timestamps, log levels, and module names. Provides a reusable `get_logger()` helper. |
| `app/db/mongodb.py` | Implements `MongoManager` using PyMongo's asynchronous driver (`AsyncMongoClient`). Manages connection pools, graceful shutdowns, and database ping checks with timeouts. |
| `app/api/endpoints/health.py` | Exposes the `/health` endpoint under `/api/v1` returning application status, release version, environment, and MongoDB connection health. |
| `app/schemas/health.py` | Defines Pydantic data schemas (`HealthCheckResponse`, `DatabaseHealth`) ensuring strong typing and automatic OpenAPI documentation. |
| `app/api/api_v1/api.py` | Aggregates all v1 API routers under a unified router prefix (`/api/v1`). |
| `.env.example` | Provides a documented template of all configurable environment variables. |
| `pytest.ini` & `tests/` | Pytest setup and automated test suite verifying health endpoints, 404 responses, and configuration parsing. |

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.10 or higher (Python 3.13 supported)
- MongoDB instance (optional for initial health check, required for database persistence)

### 2. Create and Activate Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example configuration file to create your local `.env`:

```bash
cp .env.example .env
```

*(On Windows PowerShell, use `Copy-Item .env.example .env`)*

Review `.env` and update any values if needed (e.g., `MONGODB_URL`). If MongoDB is not running locally, the application starts gracefully in a degraded state and reports connection status via the health check endpoint.

---

## 🖥 Running the Application

Start the development server with Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Once running:
- **API Root:** [http://localhost:8000/](http://localhost:8000/)
- **Health Check Endpoint:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **Interactive Swagger Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🧪 Running Tests

Run the automated test suite with pytest:

```bash
pytest
```

For verbose output:

```bash
pytest -v
```

---

## 🩺 Health Check Sample Response

```json
{
  "status": "healthy",
  "app_name": "Adaptive Technical Viva & Oral Screener",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-10-22T01:20:00.000000Z",
  "database": {
    "connected": true,
    "latency_ms": 1.25,
    "database": "adaptive_viva_db",
    "error": null
  }
}
```
*(If MongoDB is offline, `"status"` will be `"degraded"` and `"connected"` will be `false` without crashing the application).*
