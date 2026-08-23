import axios from 'axios'

import type { ApiResponse, WorldData } from '../types/world'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000',
  timeout: 5000,
})

export async function fetchWorld(): Promise<WorldData> {
  const response = await api.get<ApiResponse<WorldData>>('/api/world')
  return response.data.data
}
