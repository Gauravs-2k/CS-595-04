import uuid


def _severity(category: str, title: str, source_text: str = "") -> str:
    text = f"{title} {source_text}".lower()
    if category == "missing" and "medication" in text:
        return "critical"
    if category == "unscheduled" and ("14 days" in text or "7 days" in text or "urgent" in text):
        return "critical"
    if category == "unaddressed" and "pending" in text:
        return "critical"
    if category == "changed":
        return "warning"
    if category == "missing":
        return "warning"
    return "info"


def detect_gaps(discharge: dict, pcp: dict) -> list[dict]:
    gaps: list[dict] = []

    pcp_meds_codes = {m.get("rxnorm_code") for m in pcp.get("medications", []) if m.get("rxnorm_code")}
    pcp_dx_codes = {d.get("snomed_code") for d in pcp.get("diagnoses", []) if d.get("snomed_code")}

    pcp_care_text = " ".join([c.get("description", "") for c in pcp.get("care_plan", [])]).lower()
    pcp_labs_codes = {l.get("loinc_code") for l in pcp.get("labs", []) if l.get("loinc_code")}

    for med in discharge.get("medications", []):
        if med.get("rxnorm_code") and med.get("rxnorm_code") not in pcp_meds_codes:
            title = f"Missing medication: {med.get('name', 'Unknown')}"
            gaps.append(
                {
                    "id": uuid.uuid4(),
                    "category": "missing",
                    "severity": _severity("missing", title),
                    "title": title,
                    "description": "Medication in discharge summary not present in PCP chart.",
                    "source_text": med.get("name", ""),
                    "source_line": med.get("source_line"),
                    "standard_code": med.get("rxnorm_code"),
                    "standard_system": "RxNorm",
                    "suggested_action": "Reconcile medication list and confirm prescription continuity.",
                    "resolved": False,
                }
            )

    for dx in discharge.get("diagnoses", []):
        if dx.get("snomed_code") and dx.get("snomed_code") not in pcp_dx_codes:
            title = f"Diagnosis absent from PCP list: {dx.get('text', 'Unknown')}"
            gaps.append(
                {
                    "id": uuid.uuid4(),
                    "category": "missing",
                    "severity": _severity("missing", title),
                    "title": title,
                    "description": "Diagnosis documented on discharge is not present in PCP problem list.",
                    "source_text": dx.get("text", ""),
                    "source_line": dx.get("source_line"),
                    "standard_code": dx.get("snomed_code"),
                    "standard_system": "SNOMED",
                    "suggested_action": "Add diagnosis to active problem list if clinically appropriate.",
                    "resolved": False,
                }
            )

    for ref in discharge.get("referrals", []):
        specialty = ref.get("specialty", "")
        if specialty and specialty.lower() not in pcp_care_text:
            title = f"Unscheduled referral: {specialty}"
            source_text = f"{specialty} {ref.get('urgency', '')}".strip()
            gaps.append(
                {
                    "id": uuid.uuid4(),
                    "category": "unscheduled",
                    "severity": _severity("unscheduled", title, source_text),
                    "title": title,
                    "description": "Referral found in discharge but no matching appointment in PCP care plan.",
                    "source_text": source_text,
                    "source_line": ref.get("source_line"),
                    "standard_code": None,
                    "standard_system": "SNOMED",
                    "suggested_action": "Schedule referral appointment and notify patient.",
                    "resolved": False,
                }
            )

    for task in discharge.get("follow_up_tasks", []):
        desc = task.get("description", "")
        if desc and desc.lower() not in pcp_care_text:
            title = "Unscheduled follow-up task"
            gaps.append(
                {
                    "id": uuid.uuid4(),
                    "category": "unscheduled",
                    "severity": _severity("unscheduled", title, desc),
                    "title": title,
                    "description": "Discharge follow-up task not reflected in PCP care plan.",
                    "source_text": desc,
                    "source_line": task.get("source_line"),
                    "standard_code": None,
                    "standard_system": "SNOMED",
                    "suggested_action": "Add task to care plan with target completion date.",
                    "resolved": False,
                }
            )

    pcp_meds_by_code = {m.get("rxnorm_code"): m for m in pcp.get("medications", []) if m.get("rxnorm_code")}
    for med in discharge.get("medications", []):
        code = med.get("rxnorm_code")
        if code and code in pcp_meds_by_code:
            pcp_med = pcp_meds_by_code[code]
            if med.get("dose") != pcp_med.get("dose") or med.get("frequency") != pcp_med.get("frequency"):
                title = f"Medication regimen changed: {med.get('name', 'Unknown')}"
                gaps.append(
                    {
                        "id": uuid.uuid4(),
                        "category": "changed",
                        "severity": _severity("changed", title),
                        "title": title,
                        "description": "Dose or frequency differs between discharge and PCP chart.",
                        "source_text": med.get("name", ""),
                        "source_line": med.get("source_line"),
                        "standard_code": med.get("rxnorm_code"),
                        "standard_system": "RxNorm",
                        "suggested_action": "Verify intended regimen and update chart accordingly.",
                        "resolved": False,
                    }
                )

    pcp_labs_by_code = {l.get("loinc_code"): l for l in pcp.get("labs", []) if l.get("loinc_code")}
    for lab in discharge.get("labs", []):
        code = lab.get("loinc_code")
        if code and code in pcp_labs_by_code:
            pcp_lab = pcp_labs_by_code[code]
            if lab.get("value") and pcp_lab.get("value") and lab.get("value") != pcp_lab.get("value"):
                title = f"Lab trend changed: {lab.get('name', 'Unknown')}"
                gaps.append(
                    {
                        "id": uuid.uuid4(),
                        "category": "changed",
                        "severity": _severity("changed", title),
                        "title": title,
                        "description": "Lab value differs between discharge and PCP chart.",
                        "source_text": f"{lab.get('value')} -> {pcp_lab.get('value')}",
                        "source_line": lab.get("source_line"),
                        "standard_code": lab.get("loinc_code"),
                        "standard_system": "LOINC",
                        "suggested_action": "Review trend and repeat test if clinically indicated.",
                        "resolved": False,
                    }
                )

    for lab in discharge.get("labs", []):
        if lab.get("status") == "pending":
            code = lab.get("loinc_code")
            if not code or code not in pcp_labs_codes:
                title = f"Pending lab unaddressed: {lab.get('name', 'Unknown')}"
                gaps.append(
                    {
                        "id": uuid.uuid4(),
                        "category": "unaddressed",
                        "severity": _severity("unaddressed", title, "pending"),
                        "title": title,
                        "description": "Pending discharge lab has no corresponding PCP follow-up order.",
                        "source_text": lab.get("name", ""),
                        "source_line": lab.get("source_line"),
                        "standard_code": code,
                        "standard_system": "LOINC",
                        "suggested_action": "Place follow-up order and assign result review owner.",
                        "resolved": False,
                    }
                )

    return gaps
