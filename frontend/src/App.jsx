import { Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout.jsx";
import { ProtectedRoute } from "./components/ui.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Upload from "./pages/Upload.jsx";
import Progress from "./pages/Progress.jsx";
import Results from "./pages/Results.jsx";
import History from "./pages/History.jsx";
import DocumentDetails from "./pages/DocumentDetails.jsx";
import Reports from "./pages/Reports.jsx";
import Profile from "./pages/Profile.jsx";
import Admin from "./pages/Admin.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/documents/:id/progress" element={<Progress />} />
        <Route path="/documents/:id" element={<DocumentDetails />} />
        <Route path="/analysis/:id" element={<Results />} />
        <Route path="/history" element={<History />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/admin" element={<ProtectedRoute role="admin"><Admin /></ProtectedRoute>} />
      </Route>
      <Route path="*" element={<div className="p-10 text-center text-muted">Page not found.</div>} />
    </Routes>
  );
}
