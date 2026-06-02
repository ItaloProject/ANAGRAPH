import axios from 'axios'

// Dev: usa proxy do Quasar (/api → localhost:8001)
// Prod: usa VITE_API_BASE apontando para o backend no Render
const BASE = (import.meta.env.VITE_API_BASE as string) ?? '/api'

export const api = axios.create({ baseURL: BASE })
