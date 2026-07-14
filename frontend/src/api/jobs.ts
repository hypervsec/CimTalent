import { api } from "./client";
import type { Job, Page } from "../types/api";
export const jobsApi = {
  list: () => api.get<Page<Job>>("/jobs").then((r) => r.data),
  get: (id: string) => api.get<Job>(`/jobs/${id}`).then((r) => r.data),
  create: (data: object) => api.post<Job>("/jobs", data).then((r) => r.data),
  parse: (id: string) => api.post(`/jobs/${id}/parse`).then((r) => r.data),
};
