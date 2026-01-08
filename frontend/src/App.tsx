import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useSleepScoringStore } from "@/store";
import { Layout } from "@/components/layout";
import { LoginPage } from "@/pages/login";
import { ScoringPage } from "@/pages/scoring";
import { StudySettingsPage } from "@/pages/study-settings";
import { DataSettingsPage } from "@/pages/data-settings";
import { ExportPage } from "@/pages/export";

/**
 * Protected route wrapper - redirects to login if not authenticated
 */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useSleepScoringStore((state) => state.isAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

/**
 * Main App component with routing
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected routes with layout */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/scoring" replace />} />
          <Route path="scoring" element={<ScoringPage />} />
          <Route path="export" element={<ExportPage />} />
          <Route path="settings/study" element={<StudySettingsPage />} />
          <Route path="settings/data" element={<DataSettingsPage />} />
        </Route>

        {/* Catch-all redirect */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
