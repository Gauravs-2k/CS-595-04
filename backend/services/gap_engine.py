import uuid

from services.clinical_standards_agent import detect_clinical_standard_gaps
from services.normalize import (
    extract_specialty,
    fuzzy_match,
    medication_classes,
    normalize_dx_text,
    normalize_med_name,
)

_HIGH_RISK_MED_KEYWORDS = {
    "insulin", "warfarin", "heparin", "enoxaparin", "apixaban", "rivaroxaban",
    "dabigatran", "clopidogrel", "digoxin", "amiodarone", "prednisone",
}
_LOW_RISK_MED_KEYWORDS = {
    "acetaminophen", "paracetamol", "ibuprofen", "naproxen",
}
_DIAGNOSIS_NOISE_TERMS = {
    "chronic disease management", "disease management", "management",
    "edema", "mild bilateral ankle edema", "ankle edema",
    "chronic disease", "chronic conditions",
}


def _severity(category: str, title: str, source_text: str = "") -> str:
    text = f"{title} {source_text}".lower()
    if category == "action_needed" and "allergy" in text and "conflict" in text:
        return "critical"
    if category == "action_needed" and ("14 days" in text or "7 days" in text or "urgent" in text):
        return "critical"
    if category == "action_needed" and "pending" in text:
        return "critical"
    if category == "action_needed" and ("follow-up" in text or "referral" in text):
        return "warning"
    if category == "action_needed" and (
        "corticosteroid" in text
        or "vte" in text
        or "prophylaxis" in text
        or "standard of care" in text
        or "guideline" in text
    ):
        return "warning"
    if category == "missing_from_pcp" and "medication" in text:
        if any(k in text for k in _LOW_RISK_MED_KEYWORDS):
            return "info"
        if any(k in text for k in _HIGH_RISK_MED_KEYWORDS):
            return "critical"
        return "warning"
    if category == "missing_from_handoff" and "medication" in text:
        return "warning"
    if category == "changed":
        return "warning"
    if category == "missing_from_pcp":
        return "warning"
    if category == "missing_from_handoff":
        return "info"
    return "info"


def _build_med_sets(meds: list[dict]) -> tuple[set[str], set[str]]:
    codes = {m.get("rxnorm_code") for m in meds if m.get("rxnorm_code")}
    names = {normalize_med_name(m.get("name", "")) for m in meds if m.get("name")}
    names.discard("")
    return codes, names


def _build_dx_sets(diagnoses: list[dict]) -> tuple[set[str], set[str]]:
    codes = {d.get("snomed_code") for d in diagnoses if d.get("snomed_code")}
    texts = {normalize_dx_text(d.get("text", "")) for d in diagnoses if d.get("text")}
    texts.discard("")
    return codes, texts


def _med_in_list(med: dict, target_codes: set[str], target_names: set[str]) -> bool:
    code = med.get("rxnorm_code")
    if code and code in target_codes:
        return True
    name = normalize_med_name(med.get("name", ""))
    if not name:
        return True
    if name in target_names:
        return True
    return any(fuzzy_match(name, n) for n in target_names)


def _dx_in_list(dx: dict, target_codes: set[str], target_texts: set[str]) -> bool:
    code = dx.get("snomed_code")
    if code and code in target_codes:
        return True
    text = normalize_dx_text(dx.get("text", ""))
    if not text:
        return True
    if text in target_texts:
        return True
    return any(fuzzy_match(text, t) for t in target_texts)


def _find_matching_med(med: dict, target_meds: list[dict]) -> dict | None:
    code = med.get("rxnorm_code")
    if code:
        for tm in target_meds:
            if tm.get("rxnorm_code") == code:
                return tm
    name = normalize_med_name(med.get("name", ""))
    if name:
        for tm in target_meds:
            tm_name = normalize_med_name(tm.get("name", ""))
            if tm_name and fuzzy_match(name, tm_name):
                return tm
    return None


def _gap(category, severity_cat, title, description, source_text,
         source_line=None, standard_code=None, standard_system=None,
         suggested_action=""):
    return {
        "id": uuid.uuid4(),
        "category": category,
        "severity": _severity(severity_cat, title, source_text),
        "title": title,
        "description": description,
        "source_text": source_text,
        "source_line": source_line,
        "standard_code": standard_code,
        "standard_system": standard_system,
        "suggested_action": suggested_action,
        "resolved": False,
    }


def _allergy_conflict_gaps(discharge_meds: list[dict], allergies: list[dict]) -> list[dict]:
    gaps: list[dict] = []
    seen_conflicts = set()

    for med in discharge_meds:
        med_name = med.get("name", "")
        med_classes = medication_classes(med_name)
        if not med_name or not med_classes:
            continue

        for allergy in allergies:
            allergen = (allergy.get("name") or allergy.get("text") or "").strip()
            if not allergen:
                continue

            allergy_classes = medication_classes(allergen)
            overlap = med_classes & allergy_classes
            if not overlap:
                continue

            key = (normalize_med_name(med_name), allergen.lower())
            if key in seen_conflicts:
                continue
            seen_conflicts.add(key)

            class_text = ", ".join(sorted(overlap))
            gaps.append(_gap(
                category="action_needed",
                severity_cat="action_needed",
                title=f"Allergy conflict risk: {med_name}",
                description=(
                    "Discharge medication may conflict with documented allergy "
                    f"({allergen}) via shared class ({class_text})."
                ),
                source_text=f"{med_name} vs allergy: {allergen}",
                source_line=med.get("source_line"),
                standard_code=med.get("rxnorm_code"),
                standard_system="RxNorm",
                suggested_action="Urgent safety review: verify allergy-safe alternative before continuation.",
            ))

    return gaps


def _is_noise_dx(dx_text: str, discharge_dx_texts: set[str]) -> bool:
    norm = normalize_dx_text(dx_text)
    if not norm:
        return True
    if norm in {"disease", "chronic", "chronic disease"}:
        return True
    if "chronic disease" in norm:
        return True
    if "edema" in norm:
        return True
    if norm in _DIAGNOSIS_NOISE_TERMS or "management" in norm:
        return True
    if norm == "infection" and any(k in d for d in discharge_dx_texts for k in ("pneumonia", "infection", "sepsis")):
        return True
    return False


def detect_gaps(discharge: dict, pcp: dict) -> list[dict]:
    gaps: list[dict] = []

    discharge_meds = discharge.get("medications", [])
    pcp_meds = pcp.get("medications", [])
    discharge_dx = discharge.get("diagnoses", [])
    pcp_dx = pcp.get("diagnoses", [])
    known_allergies = discharge.get("allergies", []) + pcp.get("allergies", [])

    pcp_med_codes, pcp_med_names = _build_med_sets(pcp_meds)
    pcp_dx_codes, pcp_dx_texts = _build_dx_sets(pcp_dx)
    discharge_med_codes, discharge_med_names = _build_med_sets(discharge_meds)
    discharge_dx_codes, discharge_dx_texts = _build_dx_sets(discharge_dx)

    pcp_care_text = " ".join(
        c.get("description", "") for c in pcp.get("care_plan", [])
    ).lower()
    pcp_labs_codes = {l.get("loinc_code") for l in pcp.get("labs", []) if l.get("loinc_code")}
    pcp_labs_names = {l.get("name", "").lower().strip() for l in pcp.get("labs", []) if l.get("name")}
    pcp_labs_names.discard("")

    # ═══════════════════════════════════════════════════════════════════════════
    # GROUP 1: In handoff, not in patient record  (missing_from_pcp)
    # New things from the hospital the PCP needs to add/act on.
    # ═══════════════════════════════════════════════════════════════════════════

    # Clinical standards omissions (not simple diff) are checked first.
    gaps.extend(detect_clinical_standard_gaps(discharge=discharge, gap_builder=_gap))

    allergy_conflicts = _allergy_conflict_gaps(discharge_meds=discharge_meds, allergies=known_allergies)
    gaps.extend(allergy_conflicts)
    conflict_med_names = {
        normalize_med_name(g.get("source_text", "").split(" vs allergy:")[0])
        for g in allergy_conflicts
        if g.get("source_text")
    }

    for med in discharge_meds:
        if normalize_med_name(med.get("name", "")) in conflict_med_names:
            continue
        if not _med_in_list(med, pcp_med_codes, pcp_med_names):
            gaps.append(_gap(
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

    for dx in discharge_dx:
        if _is_noise_dx(dx.get("text", ""), pcp_dx_texts):
            continue
        if not _dx_in_list(dx, pcp_dx_codes, pcp_dx_texts):
            gaps.append(_gap(
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

    # ═══════════════════════════════════════════════════════════════════════════
    # GROUP 2: In patient record, not in handoff  (missing_from_handoff)
    # Things on the PCP chart not mentioned in discharge — possibly dropped.
    # ═══════════════════════════════════════════════════════════════════════════

    for med in pcp_meds:
        if not _med_in_list(med, discharge_med_codes, discharge_med_names):
            gaps.append(_gap(
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

    for dx in pcp_dx:
        if _is_noise_dx(dx.get("text", ""), discharge_dx_texts):
            continue
        if not _dx_in_list(dx, discharge_dx_codes, discharge_dx_texts):
            gaps.append(_gap(
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

    # ═══════════════════════════════════════════════════════════════════════════
    # GROUP 3: Changed between documents  (changed)
    # ═══════════════════════════════════════════════════════════════════════════

    for med in discharge_meds:
        pcp_med = _find_matching_med(med, pcp_meds)
        if pcp_med:
            dose_changed = (
                med.get("dose") and pcp_med.get("dose")
                and med["dose"] != pcp_med["dose"]
            )
            freq_changed = (
                med.get("frequency") and pcp_med.get("frequency")
                and med["frequency"] != pcp_med["frequency"]
            )
            if dose_changed or freq_changed:
                desc_parts = []
                if dose_changed:
                    desc_parts.append(f"Dose: {pcp_med['dose']} → {med['dose']}")
                if freq_changed:
                    desc_parts.append(f"Frequency: {pcp_med['frequency']} → {med['frequency']}")
                gaps.append(_gap(
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

    # Lab value changes
    pcp_labs_by_code = {l.get("loinc_code"): l for l in pcp.get("labs", []) if l.get("loinc_code")}
    pcp_labs_by_name = {l.get("name", "").lower().strip(): l for l in pcp.get("labs", []) if l.get("name")}
    for lab in discharge.get("labs", []):
        code = lab.get("loinc_code")
        pcp_lab = pcp_labs_by_code.get(code) if code else None
        if not pcp_lab:
            lab_name = lab.get("name", "").lower().strip()
            pcp_lab = pcp_labs_by_name.get(lab_name)
        if pcp_lab and lab.get("value") and pcp_lab.get("value") and lab["value"] != pcp_lab["value"]:
            gaps.append(_gap(
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

    # ═══════════════════════════════════════════════════════════════════════════
    # GROUP 4: Action items  (action_needed)
    # Referrals, follow-ups, pending labs that need PCP action.
    # ═══════════════════════════════════════════════════════════════════════════

    seen_referral_specialties = set()
    for ref in discharge.get("referrals", []):
        specialty_raw = ref.get("specialty", "")
        specialty = extract_specialty(specialty_raw)
        if not specialty:
            continue
        specialty_key = specialty.lower().strip()
        # Skip generic section headers and duplicates
        if specialty_key in ("referral", "referrals", "referrals:", "consult", "consultation"):
            continue
        if specialty_key in seen_referral_specialties:
            continue
        if specialty_key in pcp_care_text:
            continue
        seen_referral_specialties.add(specialty_key)
        source_text = f"{specialty_raw} {ref.get('urgency', '')}".strip()
        gaps.append(_gap(
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

    for task in discharge.get("follow_up_tasks", []):
        desc = task.get("description", "")
        if desc and desc.lower() not in pcp_care_text:
            gaps.append(_gap(
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

    for lab in discharge.get("labs", []):
        if lab.get("status") == "pending":
            code = lab.get("loinc_code")
            name = lab.get("name", "").lower().strip()
            in_pcp = (code and code in pcp_labs_codes) or (name and name in pcp_labs_names)
            if not in_pcp:
                gaps.append(_gap(
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
