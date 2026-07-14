import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { matchesApi } from "../api/matches";
import { ErrorAlert, LoadingSpinner, ScoreBadge } from "../components/common";
import { Modal } from "../components/Modal";
import { renderRequirement } from "../lib/helpers";
import { useState } from "react";
export function MatchPage() {
  const { jobId = "" } = useParams();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["matches", jobId], queryFn: () => matchesApi.list(jobId) });
  const calculate = useMutation({
    mutationFn: () => matchesApi.calculate(jobId),
    onSuccess: () => client.invalidateQueries({ queryKey: ["matches", jobId] }),
  });
  const [selected, setSelected] = useState<string | null>(null);
  const detail = useQuery({
    queryKey: ["match", selected],
    queryFn: () => matchesApi.get(selected ?? ""),
    enabled: Boolean(selected),
  });
  const recalculate = useMutation({
    mutationFn: () => matchesApi.recalculate(selected ?? ""),
    onSuccess: () => client.invalidateQueries({ queryKey: ["matches", jobId] }),
  });
  if (query.isLoading) return <LoadingSpinner />;
  if (query.isError || !query.data) return <ErrorAlert message="Match sonuçları yüklenemedi." />;
  return (
    <section>
      <h2>Match sonuçları</h2>
      <button onClick={() => calculate.mutate()}>Tüm adayları hesapla</button>
      <table>
        <thead>
          <tr>
            <th>Aday</th>
            <th>Skor</th>
            <th>Skills</th>
          </tr>
        </thead>
        <tbody>
          {query.data.items.map((item) => (
            <tr key={item.id}>
              <td>{item.candidate_name}</td>
              <td>
                <ScoreBadge score={item.total_score} />
              </td>
              <td>{item.skill_score}</td>
              <td>
                <button onClick={() => setSelected(item.id)}>Detay</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {selected && detail.data && (
        <Modal title="Match Detayı" close={() => setSelected(null)}>
          <ScoreBadge score={detail.data.total_score} />
          <p>{detail.data.explanation}</p>
          {[
            "title_score",
            "skill_score",
            "experience_score",
            "education_score",
            "location_score",
          ].map((key) => (
            <p key={key}>
              {key}: {String(detail.data[key as keyof typeof detail.data])}
            </p>
          ))}
          <h3>Eksik gereksinimler</h3>
          {detail.data.missing_requirements.map((item, index) => (
            <p key={index}>{renderRequirement(item)}</p>
          ))}
          <button onClick={() => recalculate.mutate()}>Recalculate</button>
        </Modal>
      )}
    </section>
  );
}
