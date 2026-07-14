import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/layout";
import { CandidatesPage } from "./pages/CandidatesPage";
import { DashboardPage } from "./pages/DashboardPage";
import { CandidateDetailPage } from "./pages/CandidateDetailPage";
import { JobDetailPage } from "./pages/JobDetailPage";
import { JobFormPage } from "./pages/JobFormPage";
import { JobsPage } from "./pages/JobsPage";
import { MatchPage } from "./pages/MatchPage";
import { ShortlistPage } from "./pages/ShortlistPage";
import { QueriesPage } from "./pages/QueriesPage";
import { ResultsPage } from "./pages/ResultsPage";
export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/new" element={<JobFormPage />} />
        <Route path="jobs/:jobId" element={<JobDetailPage />} />
        <Route path="jobs/:jobId/matches" element={<MatchPage />} />
        <Route path="jobs/:jobId/shortlist" element={<ShortlistPage />} />
        <Route path="jobs/:jobId/queries" element={<QueriesPage />} />
        <Route path="jobs/:jobId/results" element={<ResultsPage />} />
        <Route path="candidates" element={<CandidatesPage />} />
        <Route path="candidates/:candidateId" element={<CandidateDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
