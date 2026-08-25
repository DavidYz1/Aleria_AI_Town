import axios from 'axios'


export function resolveApiBaseUrl(
  configuredUrl: string | undefined,
  isProduction: boolean,
): string {
  const normalizedUrl = configuredUrl?.trim()
  if (normalizedUrl) {
    return normalizedUrl
  }
  return isProduction ? '/' : 'http://127.0.0.1:8000'
}


export const api = axios.create({
  baseURL: resolveApiBaseUrl(
    import.meta.env.VITE_API_BASE_URL,
    import.meta.env.PROD,
  ),
  timeout: 5000,
})
