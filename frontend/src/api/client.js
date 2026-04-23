import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000,
})

// Separate client for long-running operations (AH document retrieval can take minutes)
const longClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 420000, // 7 minutes
})

export const searchPatients = (formData) => client.post('/patients/search', formData)

export const analyzePatient = (patientId, { handoffText, handoffFile } = {}) => {
  const form = new FormData()
  if (handoffFile) form.append('handoff_file', handoffFile)
  if (handoffText) form.append('handoff_text', handoffText)
  return longClient.post(`/analyze/${patientId}`, form)
}

export const getDemoHandoff = (patientId) => client.get(`/patients/${patientId}/demo-handoff`)

export const getSession = (sessionId) => client.get(`/analyze/${sessionId}`)

export const resolveGap = (sessionId, gapId) =>
  client.patch(`/analyze/${sessionId}/gaps/${gapId}`, { resolved: true })

export const exportPDF = (sessionId) =>
  client.get(`/export/pdf/${sessionId}`, { responseType: 'blob' })

export default client
