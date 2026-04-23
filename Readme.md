# TransitionGuard — Clinical Handoff Integrity System

TransitionGuard detects care continuity gaps between hospital discharge summaries and primary care (PCP) charts. It retrieves real patient records via the Abstractive Health HIE, extracts clinical entities using scispaCy, compares discharge vs. PCP state, and surfaces prioritized gaps with suggested actions.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **NLP / Entity Extraction** | scispaCy `en_core_sci_lg` |
| **Record Retrieval** | Abstractive Health API (HIE — Carequality + CommonWell) |
| **Record Formats** | CCDA, FHIR R4, PDF |
| **Clinical Standards** | SNOMED CT, RxNorm, LOINC |
| **Backend** | FastAPI (Python 3.11) |
| **Frontend** | React + Vite |
| **Database** | PostgreSQL (via SQLAlchemy + Alembic) |
| **Auth Proxy** | Leap of Faith (LoF) token service |
| **Data Source** | MIMIC-IV (de-identified EHR dataset) |
| **Containerization** | Docker + Docker Compose |

---

## Architecture

```
Browser (React)
    │
    ▼
FastAPI Backend
    ├── /patients/search   → LoF proxy → Abstractive Health /search-patient
    ├── /analyze/{id}      → AH /retrieve-patient-docs (poll) → ZIP → scispaCy NLP → Gap Engine
    ├── /analyze/{id}/gaps → Resolve / mark gaps
    └── /export/pdf/{id}   → ReportLab PDF generation
    │
    ├── PostgreSQL (sessions + gaps)
    └── Mock fallback (when LOF_CLIENT_ID is unset)
```

---

## Gap Detection Categories

| Category | Description |
|---|---|
| `missing` | Medication prescribed at discharge but absent from PCP chart |
| `unscheduled` | Follow-up or referral ordered but not yet booked |
| `unaddressed` | Pending lab or diagnostic result with no PCP action |

---

## Quick Start

### Prerequisites
- Docker Desktop
- Credentials from the Leap of Faith sandbox (`LOF_CLIENT_ID`, `LOF_CLIENT_SECRET`)

### 1. Configure environment

```bash
cp .env.example .env
# Fill in LOF_CLIENT_ID, LOF_CLIENT_SECRET, AH_EMAIL in .env
```

### 2. Start all services

```bash
docker-compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

### 3. Demo patient (AH sandbox)

| Field | Value |
|---|---|
| First Name | `Nwhinone` |
| Last Name | `Nwhinzzztestpatient` |
| DOB | `1981-01-01` |
| Gender | `M` |
| Phone | `205-111-1111` |
| Address | `1100 Test Street, Helena, AL 35080` |

---

## Mock Mode

If `LOF_CLIENT_ID` is empty the backend automatically serves mock data — no credentials needed. Useful for UI development and CI.

```bash
# .env with no LOF credentials → mock mode
LOF_CLIENT_ID=
```

---

## Running Tests

```bash
cd backend
pytest tests/ -v
```

---

## Project Structure

```
.
├── backend/
│   ├── routers/        # FastAPI route handlers
│   ├── services/
│   │   ├── abstractive.py      # AH API client + LoF token flow
│   │   ├── nlp.py              # scispaCy entity extraction
│   │   ├── gap_engine.py       # Gap detection logic
│   │   ├── pdf_export.py       # ReportLab PDF generation
│   │   └── mock_abstractive.py # Mock data for development
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic request/response schemas
│   └── db/             # Database setup + Alembic migrations
└── frontend/
    └── src/
        ├── pages/      # SearchPage, LoadingPage, ReportPage
        ├── components/ # PatientCard, GapItem, Sidebar, TopBar
        └── api/        # Axios client
```

---

## Course Context

CS 595-04 · Medical Informatics & AI · Illinois Institute of Technology · Spring 2026
