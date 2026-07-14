import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { jobsApi } from "../api/jobs";
import { candidatesApi } from "../api/candidates";
import { EmptyState, ErrorAlert, LoadingSpinner } from "../components/common";
import { distribution } from "../lib/helpers";
export function DashboardPage() {
  const jobs = useQuery({ queryKey: ["jobs", "dashboard"], queryFn: jobsApi.list });
  const candidates = useQuery({
    queryKey: ["candidates", "dashboard"],
    queryFn: candidatesApi.list,
  });
  if (jobs.isLoading || candidates.isLoading) return <LoadingSpinner />;
  if (jobs.isError || candidates.isError || !jobs.data || !candidates.data)
    return <ErrorAlert message="Dashboard yüklenemedi." />;
  const parsed = jobs.data.items.filter((x) =>
    ["parsed", "sourcing", "completed"].includes(x.status),
  ).length;
  const cities = distribution(candidates.data.items.map((x) => x.city));
  return (
    <section>
      <h2>Dashboard</h2>
      <div className="metrics">
        <p>Toplam ilan: {jobs.data.total_items}</p>
        <p>Parse edilmiş: {parsed}</p>
        <p>Toplam aday: {candidates.data.total_items}</p>
      </div>
      <small>Grafikler yüklenen sayfa verilerinden hesaplanmıştır.</small>
      {cities.length ? (
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={cities}>
            <XAxis dataKey="name" />
            <YAxis />
            <Bar dataKey="value" fill="#1769aa" />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState>Grafik verisi yok.</EmptyState>
      )}
    </section>
  );
}
