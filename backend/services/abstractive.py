import asyncio
import io
import json
import logging
import time
import zipfile

import httpx
from fastapi import HTTPException

from config import get_settings
from schemas.clinical import (
    ClinicalDocument,
    ClinicalEntities,
    ClinicalSummary,
    DiagnosisEntity,
    LabEntity,
    MedicationEntity,
    PatientRecords,
    SourceInfo,
)
from services import mock_abstractive

logger = logging.getLogger(__name__)

# In-process token caches: (token_str, expiry_epoch)
_lof_token_cache: tuple[str, float] | None = None
_ah_token_cache: tuple[str, float] | None = None

# patient_id → {conversation_id, name, dob}
_patient_cache: dict[str, dict] = {}


def get_patient_meta(patient_id: str) -> dict:
    return _patient_cache.get(patient_id, {})


def _use_mock() -> bool:
    return not get_settings().lof_client_id


# ── Token helpers ─────────────────────────────────────────────────────────────

async def _get_lof_token(client: httpx.AsyncClient) -> str:
    global _lof_token_cache
    if _lof_token_cache:
        token, expiry = _lof_token_cache
        if time.time() < expiry - 30:
            return token

    settings = get_settings()
    logger.info("lof: fetching access token")
    response = await client.post(
        f"{settings.lof_base_url}/generate-access-token/",
        json={"client_id": settings.lof_client_id, "client_secret": settings.lof_client_secret},
        headers={"Content-Type": "application/json"},
        timeout=15.0,
    )
    if response.status_code != 200:
        logger.error("lof: token fetch failed status=%s body=%s", response.status_code, response.text[:300])
        raise HTTPException(status_code=502, detail="Could not authenticate with LoF service")

    token = response.json()["access_token"]
    _lof_token_cache = (token, time.time() + 3300)  # 55-min cache (tokens ~1hr)
    logger.info("lof: token acquired")
    return token


async def _get_ah_token(client: httpx.AsyncClient) -> str:
    global _ah_token_cache
    if _ah_token_cache:
        token, expiry = _ah_token_cache
        if time.time() < expiry - 30:
            return token

    lof_token = await _get_lof_token(client)
    settings = get_settings()
    logger.info("lof: fetching AH token via proxy")
    response = await client.post(
        f"{settings.lof_base_url}/ah/token/",
        json={},
        headers={"Authorization": f"Bearer {lof_token}", "Content-Type": "application/json"},
        timeout=15.0,
    )
    if response.status_code != 200:
        logger.error("lof: AH token fetch failed status=%s body=%s", response.status_code, response.text[:300])
        raise HTTPException(status_code=502, detail="Could not obtain Abstractive Health token")

    token = response.json()["access_token"]
    _ah_token_cache = (token, time.time() + 3300)
    logger.info("lof: AH token acquired")
    return token


# ── Document parsing ──────────────────────────────────────────────────────────

def _extract_str(item) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return (item.get("name") or item.get("text") or item.get("description") or "").strip()
    return str(item).strip()


def _section_to_entities(section: dict) -> ClinicalEntities:
    diagnoses = [
        DiagnosisEntity(text=_extract_str(c))
        for c in (section.get("Medical History") or section.get("Conditions") or [])
        if _extract_str(c)
    ]
    medications = [
        MedicationEntity(name=_extract_str(m))
        for m in (section.get("Medications") or [])
        if _extract_str(m)
    ]
    labs = [
        LabEntity(name=_extract_str(lab), status="pending")
        for lab in (section.get("Labs") or [])
        if _extract_str(lab)
    ]
    return ClinicalEntities(diagnoses=diagnoses, medications=medications, labs=labs)


def _section_to_raw(section: dict) -> str:
    parts = []
    for key, val in section.items():
        if key == "Patient":
            continue
        if isinstance(val, list):
            items = "; ".join(_extract_str(v) for v in val if _extract_str(v))
            if items:
                parts.append(f"{key}: {items}")
        elif val:
            parts.append(f"{key}: {val}")
    return "\n".join(parts)


def _notes_to_records(notes: list[dict], patient_id: str) -> PatientRecords:
    if not notes:
        return PatientRecords(
            discharge_summary=ClinicalDocument(raw_text="No records retrieved."),
            pcp_chart=ClinicalDocument(raw_text=""),
        )

    # Most recent note = discharge; earlier notes = PCP chart history
    discharge_section = notes[0].get("section_content", {})
    pcp_notes = notes[1:]

    pcp_diagnoses, pcp_meds, pcp_raw_parts = [], [], []
    for n in pcp_notes:
        sec = n.get("section_content", {})
        entities = _section_to_entities(sec)
        pcp_diagnoses += entities.diagnoses
        pcp_meds += entities.medications
        pcp_raw_parts.append(_section_to_raw(sec))

    return PatientRecords(
        discharge_summary=ClinicalDocument(
            raw_text=_section_to_raw(discharge_section),
            structured=_section_to_entities(discharge_section),
        ),
        pcp_chart=ClinicalDocument(
            raw_text="\n".join(pcp_raw_parts),
            structured=ClinicalEntities(diagnoses=pcp_diagnoses, medications=pcp_meds),
        ),
        sources=[
            SourceInfo(
                name="Abstractive Health",
                ehr="AH Sandbox",
                retrieved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                format="cleaned_text_notes JSON",
            )
        ],
    )


def _parse_zip(zip_bytes: bytes, patient_id: str) -> PatientRecords:
    notes = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        note_files = sorted(
            f for f in z.namelist()
            if "cleaned_text_notes/" in f
            and f.endswith(".json")
            and "Progress note_" in f.split("/")[-1]
            and not f.split("/")[-1].startswith("._")
        )
        logger.info("ah: found %d note files for patient_id=%s", len(note_files), patient_id)
        for nf in note_files:
            with z.open(nf) as fh:
                try:
                    note = json.load(fh)
                except UnicodeDecodeError:
                    note = json.loads(fh.read().decode("latin-1"))
                notes.append(note)

    return _notes_to_records(notes, patient_id)


# ── Client ────────────────────────────────────────────────────────────────────

class AbstractiveClient:

    async def search_patient(self, patient_data: dict) -> list[dict]:
        if _use_mock():
            logger.info("abstractive.search_patient: mock mode")
            return mock_abstractive.search_patient(patient_data=patient_data)

        settings = get_settings()
        dob_raw = patient_data.get("dob", "")
        birth_time = dob_raw.replace("-", "")  # YYYY-MM-DD → YYYYMMDD

        payload = {
            "user_api_email": settings.ah_email,
            "token": None,  # filled below after token fetch
            "patient_metadata": [
                {
                    "demographics": {
                        "given_name": patient_data.get("first_name", ""),
                        "family_name": patient_data.get("last_name", ""),
                        "administrative_gender_code": patient_data.get("gender", ""),
                        "birth_time": birth_time,
                        "phone_number": patient_data.get("phone", ""),
                        "email": patient_data.get("email", ""),
                    },
                    "addresses": [
                        {
                            "street_address_line": patient_data.get("address", ""),
                            "city": patient_data.get("city", ""),
                            "state": patient_data.get("state", ""),
                            "postal_code": patient_data.get("zip", ""),
                            "country": patient_data.get("country", "USA"),
                        }
                    ],
                }
            ],
            "robustness": "20",
            "test": settings.ah_test_mode,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            ah_token = await _get_ah_token(client)
            payload["token"] = ah_token

            logger.info("ah: search_patient name=%s %s", patient_data.get("first_name"), patient_data.get("last_name"))
            # AH search returns 202 with processing=True but already contains patient_id — use first response directly
            response = await client.post(f"{settings.ah_base_url}/search-patient", json=payload)

        logger.info("ah: search response status=%s body=%s", response.status_code, response.text[:400])

        if response.status_code not in (200, 202):
            try:
                reason = response.json().get("failure_reason") or response.text[:200]
            except Exception:
                reason = response.text[:200]
            raise HTTPException(status_code=502, detail=f"Abstractive Health search failed: {reason}")

        data = response.json()

        if data.get("status") == "failure":
            reason = data.get("failure_reason") or "unknown"
            logger.error("ah: search failure reason=%s", reason)
            raise HTTPException(status_code=502, detail=f"Abstractive Health search failed: {reason}")

        conversation_id = data.get("conversation_id", "")
        full_name = f"{patient_data.get('first_name', '')} {patient_data.get('last_name', '')}".strip()

        results = []
        for r in data.get("results", []):
            pid = r.get("patient_id", "")
            if not pid:
                continue
            _patient_cache[pid] = {
                "conversation_id": conversation_id,
                "name": full_name,
                "dob": dob_raw,
            }
            results.append({
                "patient_id": pid,
                "name": full_name,
                "dob": dob_raw,
                "mrn": r.get("mrn", ""),
                "source_ehr": r.get("source_ehr", "Abstractive Health"),
                "last_discharge_date": r.get("last_discharge_date", ""),
            })

        logger.info("ah: search complete results=%d conversation_id=%s", len(results), conversation_id)
        return results

    async def retrieve_records(self, patient_id: str) -> PatientRecords:
        if _use_mock():
            logger.info("abstractive.retrieve_records: mock mode patient_id=%s", patient_id)
            return mock_abstractive.retrieve_records(patient_id=patient_id)

        meta = _patient_cache.get(patient_id)
        if not meta:
            raise HTTPException(status_code=400, detail=f"No search session found for patient_id={patient_id}. Search first.")

        conversation_id = meta["conversation_id"]
        settings = get_settings()

        async with httpx.AsyncClient(timeout=60.0) as client:
            ah_token = await _get_ah_token(client)

            payload = {
                "user_api_email": settings.ah_email,
                "token": ah_token,
                "conversation_id": conversation_id,
                "patient_id": patient_id,
                "test": settings.ah_test_mode,
            }

            # Poll up to 5 minutes at 20-second intervals
            deadline = time.time() + 300
            while True:
                logger.info("ah: retrieve_patient_docs patient_id=%s conversation_id=%s", patient_id, conversation_id)
                response = await client.post(f"{settings.ah_base_url}/retrieve-patient-docs", json=payload)

                if response.status_code not in (200, 202):
                    logger.error("ah: retrieve failed status=%s body=%s", response.status_code, response.text[:300])
                    try:
                        reason = response.json().get("failure_reason") or response.text[:200]
                    except Exception:
                        reason = response.text[:200]
                    raise HTTPException(status_code=502, detail=f"Abstractive Health retrieve failed: {reason}")

                docs = response.json()
                logger.info("ah: retrieve_patient_docs status=%s processing=%s", docs.get("status"), docs.get("processing"))

                if docs.get("status") == "failure":
                    reason = docs.get("failure_reason") or "unknown"
                    raise HTTPException(status_code=502, detail=f"Abstractive Health retrieve failed: {reason}")

                # Done when status is "success" and processing is explicitly False
                if docs.get("status") == "success" and not docs.get("processing", True):
                    break

                if time.time() > deadline:
                    logger.warning("ah: polling timeout for patient_id=%s", patient_id)
                    raise HTTPException(status_code=504, detail="Timed out waiting for Abstractive Health documents")

                logger.info("ah: documents still processing, waiting 10s...")
                await asyncio.sleep(10)

        if docs.get("status") != "success" or not docs.get("results"):
            raise HTTPException(status_code=502, detail="Abstractive Health returned no documents")

        result = docs["results"][0]
        url = result.get("url")
        if not url:
            raise HTTPException(status_code=502, detail="Abstractive Health document URL missing")

        logger.info("ah: downloading ZIP from url=%s", url[:60])
        async with httpx.AsyncClient(timeout=60.0) as dl_client:
            zip_response = await dl_client.get(url)
        zip_response.raise_for_status()

        return _parse_zip(zip_response.content, patient_id)

    async def get_summary(self, patient_id: str) -> ClinicalSummary:
        # Summary is derived locally; AH doesn't have a separate summary endpoint
        return mock_abstractive.get_summary(patient_id=patient_id)
