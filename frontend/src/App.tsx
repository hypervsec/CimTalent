import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/layout";
const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })),
);
const JobsPage = lazy(() => import("./pages/JobsPage").then((m) => ({ default: m.JobsPage })));
const JobFormPage = lazy(() =>
  import("./pages/JobFormPage").then((m) => ({ default: m.JobFormPage })),
);
const JobDetailPage = lazy(() =>
  import("./pages/JobDetailPage").then((m) => ({ default: m.JobDetailPage })),
);
const QueriesPage = lazy(() =>
  import("./pages/QueriesPage").then((m) => ({ default: m.QueriesPage })),
);
const ResultsPage = lazy(() =>
  import("./pages/ResultsPage").then((m) => ({ default: m.ResultsPage })),
);
const CandidatesPage = lazy(() =>
  import("./pages/CandidatesPage").then((m) => ({ default: m.CandidatesPage })),
);
const CandidateDetailPage = lazy(() =>
  import("./pages/CandidateDetailPage").then((m) => ({ default: m.CandidateDetailPage })),
);
const MatchPage = lazy(() => import("./pages/MatchPage").then((m) => ({ default: m.MatchPage })));
const ShortlistPage = lazy(() =>
  import("./pages/ShortlistPage").then((m) => ({ default: m.ShortlistPage })),
);
export function App() {
  return (
    <Suspense fallback={<p>Yükleniyor…</p>}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="jobs/new" element={<JobFormPage />} />
          <Route path="jobs/:jobId" element={<JobDetailPage />} />
          <Route path="jobs/:jobId/queries" element={<QueriesPage />} />
          <Route path="jobs/:jobId/results" element={<ResultsPage />} />
          <Route path="jobs/:jobId/matches" element={<MatchPage />} />
          <Route path="jobs/:jobId/shortlist" element={<ShortlistPage />} />
          <Route path="candidates" element={<CandidatesPage />} />
          <Route path="candidates/:candidateId" element={<CandidateDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
