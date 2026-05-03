import logging
from collections.abc import Callable

from config import get_settings
from services.clinical_standards_agent import detect_clinical_standard_gaps
from services import gap_engine
from services.normalize import extract_specialty

logger = logging.getLogger(__name__)

try:
    from langchain_core.runnables import RunnableLambda, RunnableParallel  # type: ignore[reportMissingImports]
    _LANGCHAIN_AVAILABLE = True
except Exception:  # pragma: no cover - defensive fallback
    RunnableLambda = None
    RunnableParallel = None
    _LANGCHAIN_AVAILABLE = False


def _build_context(discharge: dict, pcp: dict) -> dict:
    discharge_meds = discharge.get("medications", [])
    pcp_meds = pcp.get("medications", [])
    discharge_dx = discharge.get("diagnoses", [])
    pcp_dx = pcp.get("diagnoses", [])
    known_allergies = discharge.get("allergies", []) + pcp.get("allergies", [])

    pcp_med_codes, pcp_med_names = gap_engine._build_med_sets(pcp_meds)
    pcp_dx_codes, pcp_dx_texts = gap_engine._build_dx_sets(pcp_dx)
    discharge_med_codes, discharge_med_names = gap_engine._build_med_sets(discharge_meds)
    discharge_dx_codes, discharge_dx_texts = gap_engine._build_dx_sets(discharge_dx)

    pcp_care_text = " ".join(c.get("description", "") for c in pcp.get("care_plan", [])).lower()
    pcp_labs_codes = {l.get("loinc_code") for l in pcp.get("labs", []) if l.get("loinc_code")}
    pcp_labs_names = {l.get("name", "").lower().strip() for l in pcp.get("labs", []) if l.get("name")}
    pcp_labs_names.discard("")

    return {
        "discharge": discharge,
        "pcp": pcp,
        "discharge_meds": discharge_meds,
        "pcp_meds": pcp_meds,
        "discharge_dx": discharge_dx,
        "pcp_dx": pcp_dx,
        "known_allergies": known_allergies,
        "pcp_med_codes": pcp_med_codes,
        "pcp_med_names": pcp_med_names,
        "pcp_dx_codes": pcp_dx_codes,
        "pcp_dx_texts": pcp_dx_texts,
        "discharge_med_codes": discharge_med_codes,
        "discharge_med_names": discharge_med_names,
        "discharge_dx_codes": discharge_dx_codes,
        "discharge_dx_texts": discharge_dx_texts,
        "pcp_care_text": pcp_care_text,
        "pcp_labs_codes": pcp_labs_codes,
        "pcp_labs_names": pcp_labs_names,
    }


def _medication_agent(ctx: dict) -> list[dict]:
    gaps: list[dict] = []

    allergy_conflicts = gap_engine._allergy_conflict_gaps(
        discharge_meds=ctx["discharge_meds"],
        allergies=ctx["known_allergies"],
    )
    gaps.extend(allergy_conflicts)
    conflict_med_names = {
        gap_engine.normalize_med_name(g.get("source_text", "").split(" vs allergy:")[0])
        for g in allergy_conflicts
        if g.get("source_text")
    }

    for med in ctx["discharge_meds"]:
        if gap_engine.normalize_med_name(med.get("name", "")) in conflict_med_names:
            continue
        if not gap_engine._med_in_list(med, ctx["pcp_med_codes"], ctx["pcp_med_names"]):
            gaps.append(gap_engine._gap(
                category="missing_from_pcp",
                severity_cat="missing_from_pcp",
                title=f"New medication: {med.get('name', 'Unknown')}",
                description="Prescribed at discharge but not in the patient's existing medication list.",
                source_text=med.get("name", ""),
                source_line=med.get("source_line"),
                standard_code=med.get("rxnorm_code"),
                standard_system="RxNorm",
                suggested_action="Add to medication list and confirm prescription continuity.",
            ))

    for med in ctx["pcp_meds"]:
        if not gap_engine._med_in_list(med, ctx["discharge_med_codes"], ctx["discharge_med_names"]):
            gaps.append(gap_engine._gap(
                category="missing_from_handoff",
                severity_cat="missing_from_handoff",
                title=f"Medication not in handoff: {med.get('name', 'Unknown')}",
                description="On patient's existing medication list but not mentioned in the discharge summary. May have been intentionally discontinued or omitted.",
                source_text=med.get("name", ""),
                source_line=med.get("source_line"),
                standard_code=med.get("rxnorm_code"),
                standard_system="RxNorm",
                suggested_action="Verify whether medication was discontinued or inadvertently omitted.",
            ))

    for med in ctx["discharge_meds"]:
        pcp_med = gap_engine._find_matching_med(med, ctx["pcp_meds"])
        if pcp_med:
            dose_changed = med.get("dose") and pcp_med.get("dose") and med["dose"] != pcp_med["dose"]
            freq_changed = (
                med.get("frequency") and pcp_med.get("frequency") and med["frequency"] != pcp_med["frequency"]
            )
            if dose_changed or freq_changed:
                desc_parts = []
                if dose_changed:
                    desc_parts.append(f"Dose: {pcp_med['dose']} → {med['dose']}")
                if freq_changed:
                    desc_parts.append(f"Frequency: {pcp_med['frequency']} → {med['frequency']}")
                gaps.append(gap_engine._gap(
                    category="changed",
                    severity_cat="changed",
                    title=f"Regimen changed: {med.get('name', 'Unknown')}",
                    description=". ".join(desc_parts) + ".",
                    source_text=med.get("name", ""),
                    source_line=med.get("source_line"),
                    standard_code=med.get("rxnorm_code"),
                    standard_system="RxNorm",
                    suggested_action="Verify intended regimen and update chart accordingly.",
                ))

    return gaps


def _clinical_standards_agent(ctx: dict) -> list[dict]:
    return detect_clinical_standard_gaps(discharge=ctx["discharge"], gap_builder=gap_engine._gap)


def _diagnosis_agent(ctx: dict) -> list[dict]:
    gaps: list[dict] = []

    for dx in ctx["discharge_dx"]:
        if gap_engine._is_noise_dx(dx.get("text", ""), ctx["pcp_dx_texts"]):
            continue
        if not gap_engine._dx_in_list(dx, ctx["pcp_dx_codes"], ctx["pcp_dx_texts"]):
            gaps.append(gap_engine._gap(
                category="missing_from_pcp",
                severity_cat="missing_from_pcp",
                title=f"New diagnosis: {dx.get('text', 'Unknown')}",
                description="Documented on discharge but not in the patient's problem list.",
                source_text=dx.get("text", ""),
                source_line=dx.get("source_line"),
                standard_code=dx.get("snomed_code"),
                standard_system="SNOMED",
                suggested_action="Add to active problem list if clinically appropriate.",
            ))

    for dx in ctx["pcp_dx"]:
        if gap_engine._is_noise_dx(dx.get("text", ""), ctx["discharge_dx_texts"]):
            continue
        if not gap_engine._dx_in_list(dx, ctx["discharge_dx_codes"], ctx["discharge_dx_texts"]):
            gaps.append(gap_engine._gap(
                category="missing_from_handoff",
                severity_cat="missing_from_handoff",
                title=f"Diagnosis not in handoff: {dx.get('text', 'Unknown')}",
                description="On patient's existing problem list but not mentioned in the discharge summary.",
                source_text=dx.get("text", ""),
                source_line=dx.get("source_line"),
                standard_code=dx.get("snomed_code"),
                standard_system="SNOMED",
                suggested_action="Confirm whether condition was addressed during hospitalization.",
            ))

    return gaps


def _lab_agent(ctx: dict) -> list[dict]:
    gaps: list[dict] = []

    pcp_labs_by_code = {l.get("loinc_code"): l for l in ctx["pcp"].get("labs", []) if l.get("loinc_code")}
    pcp_labs_by_name = {l.get("name", "").lower().strip(): l for l in ctx["pcp"].get("labs", []) if l.get("name")}

    for lab in ctx["discharge"].get("labs", []):
        code = lab.get("loinc_code")
        pcp_lab = pcp_labs_by_code.get(code) if code else None
        if not pcp_lab:
            lab_name = lab.get("name", "").lower().strip()
            pcp_lab = pcp_labs_by_name.get(lab_name)

        if pcp_lab and lab.get("value") and pcp_lab.get("value") and lab["value"] != pcp_lab["value"]:
            gaps.append(gap_engine._gap(
                category="changed",
                severity_cat="changed",
                title=f"Lab trend changed: {lab.get('name', 'Unknown')}",
                description=f"Value changed: {pcp_lab.get('value')} → {lab.get('value')}.",
                source_text=f"{pcp_lab.get('value')} → {lab.get('value')}",
                source_line=lab.get("source_line"),
                standard_code=lab.get("loinc_code"),
                standard_system="LOINC",
                suggested_action="Review trend and repeat test if clinically indicated.",
            ))

        if lab.get("status") == "pending":
            name = lab.get("name", "").lower().strip()
            in_pcp = (code and code in ctx["pcp_labs_codes"]) or (name and name in ctx["pcp_labs_names"])
            if not in_pcp:
                gaps.append(gap_engine._gap(
                    category="action_needed",
                    severity_cat="action_needed",
                    title=f"Pending result: {lab.get('name', 'Unknown')}",
                    description="Pending lab from discharge with no corresponding follow-up order.",
                    source_text=lab.get("name", ""),
                    source_line=lab.get("source_line"),
                    standard_code=code,
                    standard_system="LOINC",
                    suggested_action="Place follow-up order and assign result review owner.",
                ))

    return gaps


def _followup_agent(ctx: dict) -> list[dict]:
    gaps: list[dict] = []

    seen_referral_specialties = set()
    for ref in ctx["discharge"].get("referrals", []):
        specialty_raw = ref.get("specialty", "")
        specialty = extract_specialty(specialty_raw)
        if not specialty:
            continue
        specialty_key = specialty.lower().strip()
        if specialty_key in ("referral", "referrals", "referrals:", "consult", "consultation"):
            continue
        if specialty_key in seen_referral_specialties:
            continue
        if specialty_key in ctx["pcp_care_text"]:
            continue
        seen_referral_specialties.add(specialty_key)
        source_text = f"{specialty_raw} {ref.get('urgency', '')}".strip()
        gaps.append(gap_engine._gap(
            category="action_needed",
            severity_cat="action_needed",
            title=f"Referral to schedule: {specialty.title()}",
            description="Referral ordered at discharge but no matching appointment in patient's care plan.",
            source_text=source_text,
            source_line=ref.get("source_line"),
            standard_code=None,
            standard_system="SNOMED",
            suggested_action="Schedule referral appointment and notify patient.",
        ))

    for task in ctx["discharge"].get("follow_up_tasks", []):
        desc = task.get("description", "")
        if not desc:
            continue
        if desc.lower() in ctx["pcp_care_text"]:
            continue

        gaps.append(gap_engine._gap(
            category="action_needed",
            severity_cat="action_needed",
            title="Follow-up to schedule",
            description="Discharge follow-up task not yet reflected in patient's care plan.",
            source_text=desc,
            source_line=task.get("source_line"),
            standard_code=None,
            standard_system="SNOMED",
            suggested_action="Add task to care plan with target completion date.",
        ))

    return gaps


def _run_rule_agents(ctx: dict) -> list[dict]:
    agents: list[Callable[[dict], list[dict]]] = [
        _clinical_standards_agent,
        _medication_agent,
        _diagnosis_agent,
        _lab_agent,
        _followup_agent,
    ]
    all_gaps: list[dict] = []
    for fn in agents:
        all_gaps.extend(fn(ctx))
    return all_gaps


def _run_langchain_agents(ctx: dict) -> list[dict]:
    if not _LANGCHAIN_AVAILABLE:
        raise RuntimeError("LangChain not available")

    graph = RunnableParallel(
        standards=RunnableLambda(_clinical_standards_agent),
        medication=RunnableLambda(_medication_agent),
        diagnosis=RunnableLambda(_diagnosis_agent),
        labs=RunnableLambda(_lab_agent),
        followup=RunnableLambda(_followup_agent),
    )
    result = graph.invoke(ctx)
    return [gap for bucket in result.values() for gap in bucket]


def detect_gaps(discharge: dict, pcp: dict) -> list[dict]:
    """Detect gaps with optional LangChain orchestration over rule-based agents."""
    ctx = _build_context(discharge=discharge, pcp=pcp)
    settings = get_settings()

    if not settings.use_langchain_agents:
        return _run_rule_agents(ctx)

    try:
        return _run_langchain_agents(ctx)
    except Exception as exc:  # pragma: no cover - runtime safety fallback
        logger.warning("LangChain agent orchestration failed, falling back to rule engine: %s", exc)
        return _run_rule_agents(ctx)
