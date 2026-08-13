import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import { AuthProvider } from "./features/auth/useAuth";
import { LoginPage } from "./features/auth/LoginPage";
import { MfaPage } from "./features/auth/MfaPage";
import { ProtectedRoute } from "./features/auth/ProtectedRoute";
import { LessonPage } from "./features/lessons/LessonPage";
import { NotesPage } from "./features/notes/NotesPage";
import { NoteDetailPage } from "./features/notes/NoteDetailPage";
import { ReviewPage } from "./features/reviews/ReviewPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { FocusSessionProvider } from "./features/focus/useFocusSession";
import { FocusWidgets } from "./features/focus/FocusWidgets";
import { RecommendationButton } from "./features/focus/RecommendationButton";
import { LabsPage } from "./features/labs/LabsPage";
import { LabInstancePage } from "./features/labs/LabInstancePage";

function Home() {
  return <h1>Dashboard (placeholder)</h1>;
}

function ProtectedLayout() {
  return (
    <>
      <FocusWidgets />
      <RecommendationButton />
      <Outlet />
    </>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <FocusSessionProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/mfa" element={<MfaPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<ProtectedLayout />}>
                <Route path="/" element={<Home />} />
                <Route path="/lessons/:slug" element={<LessonPage />} />
                <Route path="/notes" element={<NotesPage />} />
                <Route path="/notes/:id" element={<NoteDetailPage />} />
                <Route path="/review" element={<ReviewPage />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/labs" element={<LabsPage />} />
                <Route path="/labs/:labId" element={<LabInstancePage />} />
              </Route>
            </Route>
          </Routes>
        </FocusSessionProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
