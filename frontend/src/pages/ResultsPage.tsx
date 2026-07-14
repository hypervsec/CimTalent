import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queriesApi } from "../api/queries";
import { searchResultsApi } from "../api/searchResults";
import { ErrorAlert, LoadingSpinner } from "../components/common";
export function ResultsPage() {
  const { jobId = "" } = useParams();
  const client = useQueryClient();
  const [queryId, setQueryId] = useState("");
  const [format, setFormat] = useState("json");
  const [payload, setPayload] = useState("[]");
  const queries = useQuery({ queryKey: ["queries", jobId], queryFn: () => queriesApi.list(jobId) });
  const results = useQuery({
    queryKey: ["results", jobId],
    queryFn: () => searchResultsApi.listJob(jobId),
  });
  const importMutation = useMutation({
    mutationFn: () => {
      if (!queryId || !payload.trim()) throw new Error("Sorgu ve içerik zorunlu");
      if (format === "json" && !Array.isArray(JSON.parse(payload)))
        throw new Error("JSON dizi olmalı");
      return searchResultsApi.import(queryId, { format, mode: "merge", payload });
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["results", jobId] }),
  });
  const bulk = useMutation({
    mutationFn: () =>
      searchResultsApi.bulk(jobId, { only_unassigned: true, max_results: 100, dry_run: false }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["results", jobId] }),
  });
  if (results.isLoading || queries.isLoading) return <LoadingSpinner />;
  if (results.isError || !results.data) return <ErrorAlert message="Sonuçlar yüklenemedi." />;
  return (
    <section>
      <h2>Search Results</h2>
      <select value={queryId} onChange={(e) => setQueryId(e.target.value)}>
        <option value="">Sorgu seçin</option>
        {queries.data?.map((q) => (
          <option key={q.id} value={q.id}>
            {q.query_text}
          </option>
        ))}
      </select>
      <select value={format} onChange={(e) => setFormat(e.target.value)}>
        <option value="json">JSON</option>
        <option value="urls">URL listesi</option>
        <option value="html">HTML</option>
      </select>
      <textarea value={payload} onChange={(e) => setPayload(e.target.value)} maxLength={200000} />
      <button onClick={() => importMutation.mutate()} disabled={!queryId}>
        İçe aktar
      </button>
      <button onClick={() => bulk.mutate()}>Toplu Aday Keşfet</button>
      {importMutation.error && <ErrorAlert message="İçe aktarma doğrulanamadı." />}
      <table>
        <tbody>
          {results.data.items.map((r) => (
            <tr key={r.id}>
              <td>{r.title}</td>
              <td>
                <a href={r.source_url} target="_blank" rel="noreferrer">
                  URL
                </a>
              </td>
              <td>
                <button onClick={() => searchResultsApi.discover(r.id)}>Aday keşfet</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
