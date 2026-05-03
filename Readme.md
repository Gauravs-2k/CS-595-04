# TransitionGuard — Clinical Handoff Integrity System

TransitionGuard detects care continuity gaps between hospital discharge summaries and primary care (PCP) charts. It retrieves real patient records via the Abstractive Health HIE, extracts clinical entities using scispaCy, compares discharge vs. PCP state, and surfaces prioritized gaps with suggested actions.

---

## Technical Workflow

This project follows a 5-step clinical handoff pipeline. Current runtime behavior is:

**Step 1: Entity Extraction**
- Runs on both `patient_history.md` and `discharge_summary.md`.
- Uses scispaCy NER with section-aware normalization and filters.
- Optional LLM code enrichment can populate SNOMED/RxNorm/LOINC fields when configured.
- Active extracted types: diagnoses, medications, labs, referrals, follow-up tasks.

**Step 2: Gap Detection Agents**
- Rule-based agents compare baseline vs discharge entities.
    - Medication agent: omissions, dose/regimen changes, allergy conflicts.
    - Diagnosis agent: new/missing diagnosis continuity gaps.
    - Follow-up agent: unscheduled referrals/tasks.
    - Lab agent: pending/continuity lab risks.
    - Standards agent: deterministic care-standard omissions.
- Optional LangChain parallel orchestration is available.

**Step 3: Severity Tagging**
- Active runtime uses deterministic severity rules: critical, warning, info.
- LLM severity triage is considered optional/target, not default runtime.

**Step 4: Clinician Dashboard**
- Frontend displays gaps with severity, evidence, and suggested actions.
- Clinicians can review and resolve items with session audit context.

**Step 5: Evaluation**
- Detected gaps are compared against ground truth per dataset case.
- Precision, Recall, and F1 are computed via the evaluation endpoint.

For the full implementation detail, see [TECHNICAL_WORKFLOW.md](TECHNICAL_WORKFLOW.md).

---

## Product Overview (for Non-Technical Users)

TransitionGuard is a clinical safety tool that helps ensure nothing important is lost when a patient leaves the hospital. It works like this:

1. **Reads both the hospital discharge summary and the patient’s long-term medical record.**
2. **Finds all the diagnoses, medications, lab results, and follow-up instructions in both documents.**
3. **Automatically flags anything new, missing, or changed—like a new medication that isn’t in the old chart, or a follow-up that wasn’t scheduled.**
4. **Shows these “gaps” in a dashboard for the clinician to review, mark as resolved, or export as a report.**
5. **For demo/testing, it can score itself against a gold-standard answer key, so you know how well it’s working.**

TransitionGuard helps clinicians catch dropped diagnoses, missed follow-ups, and medication mismatches—making handoffs safer and more reliable.

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
| `missing_from_pcp` | New medication/diagnosis in discharge not present in PCP chart |
| `missing_from_handoff` | Existing PCP medication/diagnosis not present in discharge summary |
| `changed` | Medication regimen or lab trend changed between documents |
| `action_needed` | Follow-ups/referrals/pending results that require action |

---

## Dataset Evaluation

After analyzing a dataset patient session, run:

```bash
GET /evaluation/run/{session_id}
```

The endpoint returns precision, recall, F1, and TP/FP/FN against the dataset ground truth.

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
