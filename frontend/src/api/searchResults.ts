import { api } from "./client";
export type SearchResult = {
  id: string;
  title?: string;
  source_url: string;
  displayed_name?: string;
  source_domain?: string;
  candidate_id?: string | null;
};
export const searchResultsApi = {
  listJob: (jobId: string) =>
    api.get<{ items: SearchResult[] }>(`/jobs/${jobId}/search-results`).then((r) => r.data),
  import: (queryId: string, data: object) => api.post(`/queries/${queryId}/import-results`, data),
  discover: (id: string) => api.post(`/search-results/${id}/discover-candidate`),
  bulk: (jobId: string, data: object) => api.post(`/jobs/${jobId}/candidates/discover`, data),
  delete: (id: string) => api.delete(`/search-results/${id}`),
};
