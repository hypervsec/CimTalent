import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { shortlistApi } from "../api/shortlist";
import { ErrorAlert, LoadingSpinner, ScoreBadge, StatusBadge } from "../components/common";

const statuses = ["shortlisted", "reviewed", "rejected", "contacted"];
export function ShortlistPage() {
  const { jobId = "" } = useParams();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["shortlist", jobId],
    queryFn: () => shortlistApi.list(jobId),
  });
  const refresh = () => client.invalidateQueries({ queryKey: ["shortlist", jobId] });
  const update = useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => shortlistApi.update(id, data),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: shortlistApi.delete, onSuccess: refresh });
  const exportCsv = useMutation({
    mutationFn: () => shortlistApi.export(jobId),
    onSuccess: (blob) => shortlistApi.download(blob, jobId),
  });
  if (query.isLoading) return <LoadingSpinner />;
  if (query.isError || !query.data) return <ErrorAlert message="Shortlist yüklenemedi." />;
  return (
    <section>
      <h2>Shortlist</h2>
      <button onClick={() => exportCsv.mutate()}>CSV İndir</button>
      <table>
        <thead>
          <tr>
            <th>Aday</th>
            <th>Skor</th>
            <th>Durum</th>
            <th>Not</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {query.data.items.map((item) => (
            <tr key={item.id}>
              <td>
                <Link to={`/candidates/${item.candidate.id}`}>{item.candidate.full_name}</Link>
              </td>
              <td>{item.match && <ScoreBadge score={item.match.total_score} />}</td>
              <td>
                <select
                  defaultValue={item.status}
                  onChange={(event) =>
                    update.mutate({ id: item.id, data: { status: event.target.value } })
                  }
                >
                  {statuses.map((status) => (
                    <option key={status}>{status}</option>
                  ))}
                </select>
                <StatusBadge status={item.status} />
              </td>
              <td>
                <input
                  defaultValue={item.recruiter_note ?? ""}
                  onBlur={(event) =>
                    update.mutate({ id: item.id, data: { recruiter_note: event.target.value } })
                  }
                />
              </td>
              <td>
                <button
                  onClick={() => {
                    if (window.confirm("Shortlist kaydı silinsin mi?")) remove.mutate(item.id);
                  }}
                >
                  Sil
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
