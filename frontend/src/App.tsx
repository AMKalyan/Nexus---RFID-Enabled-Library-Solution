import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { visibleNav } from "./components/nav";
import { AdminPage } from "./pages/AdminPage";
import { AuditPage } from "./pages/AuditPage";
import { CataloguePage } from "./pages/CataloguePage";
import { CirculationDeskPage } from "./pages/CirculationDeskPage";
import { HealthPage } from "./pages/HealthPage";
import { ItemPage } from "./pages/ItemPage";
import { LoginPage } from "./pages/LoginPage";
import { MembersPage } from "./pages/MembersPage";
import { MyLoansPage } from "./pages/MyLoansPage";
import { OpacPage } from "./pages/OpacPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ShelfPage } from "./pages/ShelfPage";

// Charts are loaded only when the dashboard is opened.
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

function Protected() {
  const { user } = useAuth();
  return user ? <Layout /> : <Navigate to="/login" replace />;
}

/** Send each role to the first screen it is allowed to use. */
function Home() {
  const { permissions, user } = useAuth();
  const first = visibleNav(permissions, user?.typ)[0];
  return <Navigate to={first?.path ?? "/opac"} replace />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/opac" element={<OpacPage />} />
            <Route path="/opac/shelves/:code" element={<ShelfPage />} />
            <Route element={<Protected />}>
              <Route path="/" element={<Home />} />
              <Route path="/dashboard" element={<Suspense fallback={<p>Loading…</p>}><DashboardPage /></Suspense>} />
              <Route path="/circulation" element={<CirculationDeskPage />} />
              <Route path="/catalogue" element={<CataloguePage />} />
              <Route path="/items/:id" element={<ItemPage />} />
              <Route path="/members" element={<MembersPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/audit" element={<AuditPage />} />
              <Route path="/admin" element={<AdminPage />} />
              <Route path="/health" element={<HealthPage />} />
              <Route path="/my-loans" element={<MyLoansPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
