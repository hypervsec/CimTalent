import { Link, Outlet } from "react-router-dom";
export function AppLayout() {
  return (
    <div className="layout">
      <aside>
        <h1>TalentFilter AI</h1>
        <nav>
          <Link to="/">Dashboard</Link>
          <Link to="/jobs">İş İlanları</Link>
          <Link to="/candidates">Adaylar</Link>
        </nav>
      </aside>
      <main>
        <header>Recruiter Workspace</header>
        <Outlet />
      </main>
    </div>
  );
}
