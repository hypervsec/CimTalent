import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { jobsApi } from "../api/jobs";
import { EmptyState, ErrorAlert, LoadingSpinner, StatusBadge } from "../components/common";
export function JobsPage() {
  const query = useQuery({ queryKey: ["jobs"], queryFn: jobsApi.list, retry: 1 });
  if (query.isLoading) return <LoadingSpinner />;
  if (query.isError || !query.data) return <ErrorAlert message="İlanlar yüklenemedi." />;
  return (
    <section>
      <div className="page-title">
        <h2>İş İlanları</h2>
        <Link to="/jobs/new">Yeni ilan</Link>
      </div>
      {query.data.items.length === 0 ? (
        <EmptyState>Henüz ilan yok.</EmptyState>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Pozisyon</th>
              <th>Şirket</th>
              <th>Şehir</th>
              <th>Durum</th>
            </tr>
          </thead>
          <tbody>
            {query.data.items.map((job) => (
              <tr key={job.id}>
                <td>
                  <Link to={`/jobs/${job.id}`}>{job.title}</Link>
                </td>
                <td>{job.company_name}</td>
                <td>{job.city}</td>
                <td>
                  <StatusBadge status={job.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
