import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queriesApi } from "../api/queries";
import { ErrorAlert, LoadingSpinner } from "../components/common";
export function QueriesPage() {
  const { jobId = "" } = useParams();
  const client = useQueryClient();
  const q = useQuery({ queryKey: ["queries", jobId], queryFn: () => queriesApi.list(jobId) });
  const generate = useMutation({
    mutationFn: () => queriesApi.generate(jobId, { max_queries: 5, languages: ["tr", "en"] }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["queries", jobId] }),
  });
  if (q.isLoading) return <LoadingSpinner />;
  if (q.isError || !q.data) return <ErrorAlert message="Sorgular yüklenemedi." />;
  return (
    <section>
      <h2>X-Ray Sorguları</h2>
      <button onClick={() => generate.mutate()}>Sorgu üret</button>
      <table>
        <tbody>
          {q.data.map((x) => (
            <tr key={x.id}>
              <td>{x.query_text}</td>
              <td>{x.language}</td>
              <td>{x.status}</td>
              <td>
                {x.google_search_url && (
                  <a href={x.google_search_url} target="_blank" rel="noreferrer">
                    Google’da aç
                  </a>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
