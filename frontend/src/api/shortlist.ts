import { api } from "./client";
import type { Page, Shortlist } from "../types/api";
export const shortlistApi = {
  list: (jobId: string) => api.get<Page<Shortlist>>(`/jobs/${jobId}/shortlist`).then((r) => r.data),
  update: (id: string, data: object) =>
    api.patch<Shortlist>(`/shortlist/${id}`, data).then((r) => r.data),
  export: (jobId: string) =>
    api.get(`/jobs/${jobId}/shortlist/export.csv`, { responseType: "blob" }).then((r) => r.data),
  delete: (id: string) => api.delete(`/shortlist/${id}`),
  upsert: (jobId: string, candidateId: string) =>
    api.post(`/jobs/${jobId}/shortlist/${candidateId}`, { status: "shortlisted" }),
  download: (blob: Blob, jobId: string) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `shortlist-${jobId}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  },
};
