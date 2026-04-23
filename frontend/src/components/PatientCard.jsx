export default function PatientCard({ patient, onSelect }) {
  return (
    <div className="patient-card" onClick={() => onSelect(patient.patient_id)} role="button" tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onSelect(patient.patient_id)}>
      <div className="patient-card-header">
        <span className="patient-card-name">{patient.name}</span>
        <span className="patient-card-mrn">{patient.mrn || 'N/A'}</span>
      </div>
      <div className="patient-card-meta">
        <span><strong>DOB</strong> {patient.dob}</span>
        <span><strong>EHR</strong> {patient.source_ehr || 'Unknown'}</span>
        <span><strong>Last Discharge</strong> {patient.last_discharge_date || 'Unknown'}</span>
      </div>
      <div className="patient-card-cta">View Gaps &rarr;</div>
    </div>
  )
}
