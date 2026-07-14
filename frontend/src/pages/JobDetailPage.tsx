import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { jobsApi } from "../api/jobs";
import { ErrorAlert, LoadingSpinner, StatusBadge } from "../components/common";
export function JobDetailPage() {
  const { jobId = "" } = useParams();
  const client = useQueryClient();
  const job = useQuery({ queryKey: ["job", jobId], queryFn: () => jobsApi.get(jobId) });
  const parse = useMutation({
    mutationFn: () => jobsApi.parse(jobId),
    onSuccess: () => client.invalidateQueries({ queryKey: ["job", jobId] }),
  });
  if (job.isLoading) return <LoadingSpinner />;
  if (job.isError || !job.data) return <ErrorAlert message="İlan bulunamadı." />;
  return (
    <section>
      <h2>{job.data.title}</h2>
      <p>
        {job.data.company_name} · {job.data.city}
      </p>
      <StatusBadge status={job.data.status} />
      <button onClick={() => parse.mutate()} disabled={parse.isPending}>
        Parse
      </button>
      <p>{job.data.description_raw}</p>
      <nav>
        <Link to={`/jobs/${jobId}/queries`}>X-Ray sorguları</Link>
        <Link to={`/jobs/${jobId}/results`}>Sonuçlar</Link>
        <Link to={`/jobs/${jobId}/matches`}>Match sonuçları</Link>
        <Link to={`/jobs/${jobId}/shortlist`}>Shortlist</Link>
      </nav>
    </section>
  );
}
