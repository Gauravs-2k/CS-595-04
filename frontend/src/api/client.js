import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 30000,
})

export const searchPatients = (formData) => client.post('/patients/search', formData)

export const analyzePatient = (patientId) => client.post(`/analyze/${patientId}`)

export const getSession = (sessionId) => client.get(`/analyze/${sessionId}`)

export const resolveGap = (sessionId, gapId) =>
  client.patch(`/analyze/${sessionId}/gaps/${gapId}`, { resolved: true })

export const exportPDF = (sessionId) =>
  client.get(`/export/pdf/${sessionId}`, { responseType: 'blob' })

export default client
