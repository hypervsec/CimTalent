import { api } from "./client";
export type Query = {
  id: string;
  query_text: string;
  language: string;
  status: string;
  result_count: number;
  google_search_url?: string;
};
export const queriesApi = {
  list: (jobId: string) => api.get<Query[]>(`/jobs/${jobId}/queries`).then((r) => r.data),
  generate: (jobId: string, data: object) => api.post(`/jobs/${jobId}/queries/generate`, data),
  delete: (id: string) => api.delete(`/queries/${id}`),
};
