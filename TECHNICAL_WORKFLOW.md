# TransitionGuard Technical Workflow

This document mirrors the 5-step handoff pipeline and explicitly marks what is active now.

## Visual Pipeline (As Implemented)

```text
INPUTS
  patient_history.md (longitudinal baseline)
  discharge_summary.md (handoff/discharge)
            |
            v
STEP 1: ENTITY EXTRACTION
  - scispaCy + deterministic classifiers
  - Section-aware filtering and normalization
  - Optional LLM code enrichment (SNOMED/RxNorm/LOINC)
            |
            v
STEP 2: RULE AGENTS
  - Medication Agent
  - Diagnosis Agent
  - Follow-up Agent
  - Lab Agent
  - Standards Agent (deterministic omissions)
            |
            v
STEP 3: SEVERITY TAGGING
  - Deterministic severity: critical/warning/info (active)
  - LLM severity tagging (target/optional)
            |
            v
STEP 4: CLINICIAN DASHBOARD
  - Review detected gaps
  - Resolve/dismiss actions with session audit context
            |
            v
STEP 5: EVALUATION
  detected_gaps vs ground_truth
  metrics: precision/recall/F1
```

## Current Status Summary
- Active now:
  - Two-document processing (`patient_history.md` + `discharge_summary.md`)
  - Rule-based gap detection agents (medication, diagnosis, follow-up, lab)
  - Deterministic standards checks
  - Deterministic severity assignment
  - Evaluation against ground truth (precision/recall/F1)
- Not active now:
  - Procedure extraction and CPT normalization
  - LLM-based severity assignment as the default runtime path

## Step 0: Data Loading and Patient Resolution
- Dataset and MIMIC/demo patients are resolved by patient ID.
- Dataset variant-aware IDs are supported (for example `dataset-P1-V1`).
- Search supports ID-first lookup, including missing-name cases.

## Step 1: Entity Extraction (Both Documents)
- Input documents:
  - `patient_history.md` (longitudinal baseline)
  - `discharge_summary.md` (handoff/discharge state)
- Extraction runtime (active):
  - Primary NER: scispaCy
  - Section-aware filters and normalization guards
  - Optional LLM code enrichment for selected entities when configured
- Active extracted types:
  - Diagnoses
  - Medications (with available dose/frequency)
  - Labs
  - Referrals and follow-up tasks
- Standards/coding currently used:
  - Diagnoses: SNOMED-style fields (LLM enrichment optional)
  - Medications: RxNorm fields (LLM enrichment optional)
  - Labs: LOINC fields (LLM enrichment optional)
- Planned/target (not active):
  - ICD-10 canonicalization for diagnosis output
  - Procedure extraction and CPT mapping

## Step 2: Gap Detection Agents (Rule-Based)
TransitionGuard compares structured discharge entities against baseline entities using rule agents.

1. Medication Agent
- Detects omissions, regimen changes, and allergy-conflict risks.
- Includes class-level allergy conflict checks.

2. Diagnosis Agent
- Detects new diagnoses and baseline diagnoses missing from handoff.
- Applies normalization and noise suppression.

3. Follow-up Agent
- Detects unscheduled referrals and follow-up tasks not reflected in care plan context.
- Flags timing-sensitive follow-up concerns through standards rules where applicable.

4. Lab Agent
- Detects pending result continuity risks and relevant lab trend/action gaps.

5. Standards Agent (Deterministic Rules)
- Adds care-standard omissions not captured by direct entity diff.
- Current implemented rules include:
  - COPD exacerbation steroid omission checks
  - VTE prophylaxis documentation checks
  - CHF cardiology follow-up within 7 days
  - CKD + ACE/ARB monitoring continuity
  - Hip surgery weight-bearing instruction checks

## Step 3: Severity Tagging
- Active runtime:
  - Deterministic severity assignment (`critical`, `warning`, `info`) based on rule context and risk.
- Target/optional mode:
  - LLM severity triage (Urgent/Warning/Info) can be layered on top if enabled by future policy.

## Step 4: Clinician Dashboard
- The frontend shows detected gaps with severity and suggested actions.
- Users can mark gaps resolved/dismissed in workflow.
- Session-level audit context is preserved (including resolved timestamps where available).

## Step 5: Evaluation (Demo/Testing)
- `detected_gaps` from analysis sessions are compared against `ground_truth.json`.
- Metrics computed:
  - Precision
  - Recall
  - F1
- Matching behavior:
  - Category-aware token-overlap similarity scoring.

## Orchestration Modes
- Deterministic mode:
  - In-process rule engine (`gap_engine.py`).
- Agentic orchestration mode:
  - LangChain parallel orchestration (`agentic_gap_engine.py`) with deterministic fallback.

## Operational Validation Loop
1. Run analysis (`POST /analyze/{patient_id}`)
2. Validate gap quality against source text
3. Apply extraction/normalization/rule fixes
4. Re-run and regression-check prior cohorts
5. Update ground truth and run evaluation (`GET /evaluation/run/{session_id}`)
