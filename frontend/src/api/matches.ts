import { api } from "./client";
import type { Match, Page } from "../types/api";
export const matchesApi = {
  list: (jobId: string) => api.get<Page<Match>>(`/jobs/${jobId}/matches`).then((r) => r.data),
  calculate: (jobId: string) =>
    api.post<Match[]>(`/jobs/${jobId}/matches/calculate`, {}).then((r) => r.data),
  get: (id: string) => api.get<Match>(`/matches/${id}`).then((r) => r.data),
  recalculate: (id: string) => api.post<Match>(`/matches/${id}/recalculate`).then((r) => r.data),
};
