export default function PatientCard({ patient, onSelect }) {
  const displayName = patient.name || patient.variant_id || patient.patient_id
  const displayVariant = patient.variant_id || patient.patient_id

  return (
    <div className="patient-card" onClick={() => onSelect(patient.patient_id)} role="button" tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onSelect(patient.patient_id)}>
      <div className="patient-card-header">
        <span className="patient-card-name">{displayName}</span>
        <span className="patient-card-mrn">{patient.mrn || 'N/A'}</span>
      </div>
      <div className="patient-card-meta">
        <span><strong>Variant</strong> {displayVariant}</span>
        <span><strong>DOB</strong> {patient.dob}</span>
        <span><strong>EHR</strong> {patient.source_ehr || 'Unknown'}</span>
        <span><strong>Last Discharge</strong> {patient.last_discharge_date || 'Unknown'}</span>
      </div>
      <div className="patient-card-cta">View Gaps &rarr;</div>
    </div>
  )
}
