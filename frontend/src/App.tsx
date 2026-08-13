import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./features/auth/useAuth";
import { LoginPage } from "./features/auth/LoginPage";
import { MfaPage } from "./features/auth/MfaPage";
import { ProtectedRoute } from "./features/auth/ProtectedRoute";
import { LessonPage } from "./features/lessons/LessonPage";
import { NotesPage } from "./features/notes/NotesPage";
import { NoteDetailPage } from "./features/notes/NoteDetailPage";
import { ReviewPage } from "./features/reviews/ReviewPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";

function Home() {
  return <h1>Dashboard (placeholder)</h1>;
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/mfa" element={<MfaPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Home />} />
            <Route path="/lessons/:slug" element={<LessonPage />} />
            <Route path="/notes" element={<NotesPage />} />
            <Route path="/notes/:id" element={<NoteDetailPage />} />
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
