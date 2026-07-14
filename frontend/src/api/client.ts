import axios from "axios";

export type ApiError = {
  code: string;
  message: string;
  details?: object | null;
  request_id?: string;
};
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1",
});
export function parseApiError(error: unknown): ApiError {
  if (axios.isAxiosError<{ error?: ApiError }>(error) && error.response?.data.error)
    return error.response.data.error;
  return { code: "request_failed", message: "İstek tamamlanamadı." };
}
