import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Landing      from './pages/Landing';
import DesignPicker from './pages/DesignPicker';
import Terminal     from './pages/Terminal';
import Dashboard    from './pages/Dashboard';
import Minimal      from './pages/Minimal';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"          element={<Landing />} />
        <Route path="/select"    element={<DesignPicker />} />
        <Route path="/terminal"  element={<Terminal />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/minimal"   element={<Minimal />} />
        <Route path="*"          element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}