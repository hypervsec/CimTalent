import type { ReactNode } from "react";
export function LoadingSpinner() {
  return <p aria-label="Yükleniyor">Yükleniyor…</p>;
}
export function ErrorAlert({ message }: { message: string }) {
  return (
    <p role="alert" className="error">
      {message}
    </p>
  );
}
export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}
export function ScoreBadge({ score }: { score: number }) {
  return (
    <span className={score >= 80 ? "score high" : score >= 60 ? "score medium" : "score low"}>
      {Math.round(score)}
    </span>
  );
}
export function StatusBadge({ status }: { status: string }) {
  return <span className="status">{status}</span>;
}
