import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { Home } from './pages/Home';
import { ProjectView } from './pages/ProjectView';

function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <header className="app-header">
          <Link to="/" className="app-logo">
            <span className="app-logo-text">ArchLens</span>
            <span className="app-logo-tagline">Understand the system before you build the system</span>
          </Link>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm">
              API Docs
            </a>
          </div>
        </header>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/project/:id" element={<ProjectView />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
