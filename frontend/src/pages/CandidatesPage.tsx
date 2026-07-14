import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { candidatesApi } from "../api/candidates";
import { ErrorAlert, LoadingSpinner } from "../components/common";
export function CandidatesPage() {
  const query = useQuery({ queryKey: ["candidates"], queryFn: candidatesApi.list, retry: 1 });
  if (query.isLoading) return <LoadingSpinner />;
  if (query.isError || !query.data) return <ErrorAlert message="Adaylar yüklenemedi." />;
  return (
    <section>
      <h2>Adaylar</h2>
      <table>
        <thead>
          <tr>
            <th>İsim</th>
            <th>Headline</th>
            <th>Şehir</th>
            <th>Kalite</th>
          </tr>
        </thead>
        <tbody>
          {query.data.items.map((candidate) => (
            <tr key={candidate.id}>
              <td>
                <Link to={`/candidates/${candidate.id}`}>{candidate.full_name}</Link>
              </td>
              <td>{candidate.headline}</td>
              <td>{candidate.city}</td>
              <td>{candidate.data_quality_score}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
