import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { candidatesApi, candidateProfileApi } from "../api/candidates";
import { ErrorAlert, LoadingSpinner } from "../components/common";
import { Modal } from "../components/Modal";
import { parseJsonPayload } from "../lib/helpers";
import { useState } from "react";
export function CandidateDetailPage() {
  const { candidateId = "" } = useParams();
  const client = useQueryClient();
  const c = useQuery({
    queryKey: ["candidate", candidateId],
    queryFn: () => candidatesApi.get(candidateId),
  });
  const p = useQuery({
    queryKey: ["profile", candidateId],
    queryFn: () => candidateProfileApi.profile(candidateId),
  });
  const enrich = useMutation({
    mutationFn: () => candidatesApi.enrichFixture(candidateId, "software_engineer_en", "deep"),
    onSuccess: () => client.invalidateQueries({ queryKey: ["candidate", candidateId] }),
  });
  const [manual, setManual] = useState(false);
  const [payload, setPayload] = useState(
    '{"identity":{},"experiences":[],"educations":[],"skills":[],"certifications":[],"languages":[]}',
  );
  const [previewed, setPreviewed] = useState(false);
  const preview = useMutation({
    mutationFn: () =>
      candidateProfileApi.preview(candidateId, {
        ...parseJsonPayload(payload),
        mode: "deep",
        import_mode: "merge",
        identity_update_strategy: "fill_empty",
      }),
    onSuccess: () => setPreviewed(true),
  });
  const apply = useMutation({
    mutationFn: () =>
      candidateProfileApi.import(candidateId, {
        ...parseJsonPayload(payload),
        mode: "deep",
        import_mode: "merge",
        identity_update_strategy: "fill_empty",
      }),
    onSuccess: () => {
      setManual(false);
      client.invalidateQueries({ queryKey: ["candidate", candidateId] });
      client.invalidateQueries({ queryKey: ["profile", candidateId] });
    },
  });
  if (c.isLoading || p.isLoading) return <LoadingSpinner />;
  if (c.isError || !c.data) return <ErrorAlert message="Aday bulunamadı." />;
  const profile = p.data as
    | {
        experiences?: { position_title_raw: string; company_name?: string }[];
        skills?: { raw_name: string }[];
      }
    | undefined;
  return (
    <section>
      <h2>{c.data.full_name}</h2>
      <p>{c.data.headline}</p>
      <button onClick={() => enrich.mutate()}>Fixture DEEP enrichment</button>
      <button onClick={() => setManual(true)}>Manuel Enrichment</button>
      <h3>Experiences</h3>
      {profile?.experiences?.map((x, i) => (
        <p key={i}>
          {x.position_title_raw} · {x.company_name}
        </p>
      ))}
      <h3>Skills</h3>
      {profile?.skills?.map((x, i) => (
        <span key={i} className="status">
          {x.raw_name}
        </span>
      ))}
      {manual && (
        <Modal title="Manuel Enrichment" close={() => setManual(false)}>
          <textarea
            value={payload}
            onChange={(e) => {
              setPayload(e.target.value);
              setPreviewed(false);
            }}
          />
          <button onClick={() => preview.mutate()} disabled={preview.isPending}>
            Preview
          </button>
          <button onClick={() => apply.mutate()} disabled={!previewed || apply.isPending}>
            Apply
          </button>
          {preview.error && <ErrorAlert message="Geçerli bir JSON nesnesi girin." />}
          {preview.data && <pre>{JSON.stringify(preview.data, null, 2)}</pre>}
        </Modal>
      )}
    </section>
  );
}
