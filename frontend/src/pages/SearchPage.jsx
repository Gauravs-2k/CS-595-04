import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import PatientCard from '../components/PatientCard'
import TopBar from '../components/TopBar'
import { searchPatients } from '../api/client'

const EMPTY = {
  variant_id: '',
  first_name: '', last_name: '', dob: '', gender: '',
  phone: '', email: '', address: '', city: '', state: '', zip: '',
}

export default function SearchPage() {
  const [form, setForm] = useState(EMPTY)
  const [patients, setPatients] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const onSearch = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await searchPatients(form)
      const list = Array.isArray(data) ? data : []
      setPatients(list)
      if (list.length === 0) setError('No patients found. Try a Variant ID (for example P1-V3) or name + DOB.')
    } catch {
      setError('Unable to reach patient records. Check that the backend is running.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="page shell">
      <TopBar title="Clinical Handoff Integrity" subtitle="Find post-discharge patients and detect continuity gaps." />

      <section className="search-panel">
        <form onSubmit={onSearch} className="search-form">
          <label>
            Variant ID (Unique)
            <input value={form.variant_id} onChange={set('variant_id')} placeholder="P2-V3 or dataset-P2-V3" />
          </label>
          <label>
            First Name
            <input value={form.first_name} onChange={set('first_name')} placeholder="Maria" />
          </label>
          <label>
            Last Name
            <input value={form.last_name} onChange={set('last_name')} placeholder="Alvarez" />
          </label>
          <label>
            Date of Birth
            <input type="date" value={form.dob} onChange={set('dob')} />
          </label>
          <label>
            Gender
            <select value={form.gender} onChange={set('gender')}>
              <option value="">Select…</option>
              <option value="M">Male</option>
              <option value="F">Female</option>
            </select>
          </label>

          <details className="search-optional">
            <summary>Optional fields</summary>
            <div className="search-optional-grid">
              <label>Phone<input value={form.phone} onChange={set('phone')} placeholder="205-111-1111" /></label>
              <label>Email<input type="email" value={form.email} onChange={set('email')} placeholder="patient@example.com" /></label>
              <label>Address<input value={form.address} onChange={set('address')} placeholder="1100 Test Street" /></label>
              <label>City<input value={form.city} onChange={set('city')} placeholder="Helena" /></label>
              <label>State<input value={form.state} onChange={set('state')} placeholder="AL" maxLength={2} /></label>
              <label>ZIP<input value={form.zip} onChange={set('zip')} placeholder="35080" /></label>
            </div>
          </details>

          <button type="submit" className="search-submit" disabled={loading}>
            {loading ? 'Searching…' : 'Search'}
          </button>
        </form>
      </section>

      {error ? <p className="error">{error}</p> : null}

      <section className="patient-list">
        {patients.map((patient) => (
          <PatientCard key={patient.patient_id} patient={patient} onSelect={(id) => navigate(`/upload/${id}`)} />
        ))}
      </section>
    </main>
  )
}
