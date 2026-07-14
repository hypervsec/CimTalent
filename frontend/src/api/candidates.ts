import { api } from "./client";
import type { Candidate, Page } from "../types/api";
export const candidatesApi = {
  list: () => api.get<Page<Candidate>>("/candidates").then((r) => r.data),
  get: (id: string) => api.get<Candidate>(`/candidates/${id}`).then((r) => r.data),
  enrichFixture: (id: string, fixture_key: string, mode: "fast" | "deep") =>
    api.post(`/candidates/${id}/enrichment/linkedin`, {
      provider_mode: "fixture",
      fixture_key,
      mode,
    }),
};
export const candidateProfileApi = {
  profile: (id: string) => api.get(`/candidates/${id}/profile`).then((r) => r.data),
  preview: (id: string, data: object) => api.post(`/candidates/${id}/enrichment/preview`, data),
  import: (id: string, data: object) => api.post(`/candidates/${id}/enrichment/import`, data),
  runs: (id: string) => api.get(`/candidates/${id}/enrichment-runs`).then((r) => r.data),
};
