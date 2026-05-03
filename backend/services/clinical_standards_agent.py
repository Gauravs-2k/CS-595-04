"""Clinical standards rules that detect omissions not captured by simple chart diffs."""

from services.normalize import normalize_dx_text, normalize_med_name

_CORTICOSTEROID_TERMS = (
    "prednisone",
    "prednisolone",
    "methylprednisolone",
    "dexamethasone",
    "hydrocortisone",
    "corticosteroid",
    "steroid",
)

_VTE_TERMS = (
    "vte prophylaxis",
    "dvt prophylaxis",
    "venous thromboembolism prophylaxis",
    "heparin",
    "enoxaparin",
    "sequential compression",
    "compression device",
)

_NEGATIVE_VTE_CONTEXT = (
    "not documented",
    "not addressed",
    "not provided",
    "not ordered",
    "no prophylaxis",
    "without prophylaxis",
)
_VTE_RISK_TERMS = (
    "heart failure",
    "chf",
    "stroke",
    "atrial fibrillation",
    "arthroplasty",
    "hip surgery",
    "orthopedic",
    "copd exacerbation",
    "pneumonia",
    "immobil",
)


def detect_clinical_standard_gaps(discharge: dict, gap_builder) -> list[dict]:
    """Detect standards-of-care gaps using deterministic keyword/presence rules."""
    gaps: list[dict] = []

    discharge_text = (discharge.get("document_text") or "").lower()
    diagnoses = [normalize_dx_text(d.get("text", "")) for d in discharge.get("diagnoses", [])]
    med_names = [normalize_med_name(m.get("name", "")) for m in discharge.get("medications", [])]

    has_copd_exacerbation = any(
        ("copd" in dx and "exacerbation" in (d.get("text", "").lower()))
        for dx, d in zip(diagnoses, discharge.get("diagnoses", []), strict=False)
    ) or ("copd" in discharge_text and "exacerbation" in discharge_text)

    has_steroid = any(any(term in name for term in _CORTICOSTEROID_TERMS) for name in med_names)
    if has_copd_exacerbation and not has_steroid:
        gaps.append(
            gap_builder(
                category="action_needed",
                severity_cat="action_needed",
                title="No corticosteroids prescribed for COPD exacerbation",
                description=(
                    "Discharge indicates COPD exacerbation, but no systemic corticosteroid was found "
                    "in discharge medications."
                ),
                source_text="COPD exacerbation without corticosteroid (GOLD guideline)",
                source_line=None,
                standard_code=None,
                standard_system="Guideline",
                suggested_action="Review GOLD-aligned steroid plan and document rationale if intentionally omitted.",
            )
        )

    has_vte_risk = any(term in discharge_text for term in _VTE_RISK_TERMS)
    has_vte_term = any(term in discharge_text for term in _VTE_TERMS)
    has_negative_vte_context = any(term in discharge_text for term in _NEGATIVE_VTE_CONTEXT)
    has_vte_documentation = has_vte_term and not has_negative_vte_context
    if has_vte_risk and not has_vte_documentation:
        gaps.append(
            gap_builder(
                category="action_needed",
                severity_cat="action_needed",
                title="VTE prophylaxis not documented",
                description="No VTE/DVT prophylaxis plan or documentation was found in the discharge summary.",
                source_text="Missing VTE prophylaxis documentation",
                source_line=None,
                standard_code=None,
                standard_system="Hospital Standard",
                suggested_action="Document VTE prophylaxis status (pharmacologic/mechanical/contraindication).",
            )
        )

    has_chf = "heart failure" in discharge_text or "chf" in discharge_text
    has_cardiology_followup_7d = (
        ("cardiology" in discharge_text and "7 days" in discharge_text)
        or ("cardiology" in discharge_text and "within 7 days" in discharge_text)
    )
    if has_chf and not has_cardiology_followup_7d:
        gaps.append(
            gap_builder(
                category="action_needed",
                severity_cat="action_needed",
                title="No cardiology follow-up within 7 days for CHF",
                description="CHF discharge did not document early cardiology follow-up within 7 days.",
                source_text="CHF follow-up timing gap",
                source_line=None,
                standard_code=None,
                standard_system="Guideline",
                suggested_action="Arrange cardiology follow-up within 7 days for post-discharge CHF monitoring.",
            )
        )

    has_ckd = "chronic kidney disease" in discharge_text or "ckd" in discharge_text
    has_acei = any("pril" in name for name in med_names)
    has_renal_monitoring_plan = any(k in discharge_text for k in ("bmp", "creatinine", "potassium", "renal function"))
    if has_ckd and has_acei and not has_renal_monitoring_plan:
        gaps.append(
            gap_builder(
                category="action_needed",
                severity_cat="action_needed",
                title="ACE inhibitor in CKD without monitoring plan",
                description="ACE inhibitor use in CKD noted, but no renal/electrolyte monitoring follow-up was documented.",
                source_text="CKD + ACE inhibitor monitoring gap",
                source_line=None,
                standard_code=None,
                standard_system="Guideline",
                suggested_action="Document creatinine/potassium monitoring interval after discharge.",
            )
        )

    has_hip_arthroplasty = (
        "hip arthroplasty" in discharge_text
        or "total hip" in discharge_text
        or "orthopedic" in discharge_text
    )
    has_weight_bearing_instruction = "weight-bearing" in discharge_text or "weight bearing" in discharge_text
    if has_hip_arthroplasty and not has_weight_bearing_instruction:
        gaps.append(
            gap_builder(
                category="action_needed",
                severity_cat="action_needed",
                title="Weight-bearing instructions not documented after hip surgery",
                description="Discharge summary did not specify post-op weight-bearing status/instructions.",
                source_text="Post-arthroplasty weight-bearing instruction gap",
                source_line=None,
                standard_code=None,
                standard_system="Hospital Standard",
                suggested_action="Document explicit weight-bearing status (WBAT/partial/non-weight-bearing) at discharge.",
            )
        )

    return gaps