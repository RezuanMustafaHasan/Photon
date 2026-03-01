import { useCallback, useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useNavigate, useLocation } from 'react-router-dom';
import './App.css';

const API_BASE = import.meta.env.VITE_ADMIN_API_URL || 'http://localhost:5050';

const useAdminApi = () => {
  const request = useCallback(async (path, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.message || 'Request failed');
    }
    return data;
  }, []);
  return { request };
};

const PageShell = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const isUsers = location.pathname.includes('/admin/users');
  const isContents = location.pathname.includes('/admin/contents');

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <div className="app-title">Photon Admin</div>
          <div className="app-subtitle">Manage users and content</div>
        </div>
        <nav className="nav-links">
          <button className={isUsers ? 'active' : ''} onClick={() => navigate('/admin/users')}>Users</button>
          <button className={isContents ? 'active' : ''} onClick={() => navigate('/admin/contents')}>Contents</button>
        </nav>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
};

const UsersPage = () => {
  const { request } = useAdminApi();
  const [users, setUsers] = useState([]);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    const loadUsers = async () => {
      setStatus('loading');
      setError('');
      try {
        const data = await request('/api/admin/users');
        if (mounted) {
          setUsers(data.users || []);
          setStatus('ready');
        }
      } catch (err) {
        if (mounted) {
          setError(err.message);
          setStatus('error');
        }
      }
    };
    loadUsers();
    return () => {
      mounted = false;
    };
  }, [request]);

  return (
    <section className="panel">
      <h2>Users</h2>
      {status === 'loading' && <p className="muted">Loading users…</p>}
      {status === 'error' && <p className="error">{error}</p>}
      {status === 'ready' && (
        <div className="table">
          <div className="table-row table-header">
            <div>ID</div>
            <div>Name</div>
            <div>Email</div>
            <div>Role</div>
          </div>
          {users.map((user) => (
            <div key={user.id} className="table-row">
              <div>{user.id}</div>
              <div>{user.name}</div>
              <div>{user.email}</div>
              <div>{user.role}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};

const ContentsPage = () => {
  const { request } = useAdminApi();
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState('');
  const [fileContent, setFileContent] = useState('');
  const [uploadFile, setUploadFile] = useState(null);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const loadItems = useCallback(async () => {
    setStatus('loading');
    setError('');
    try {
      const data = await request('/api/admin/contents/list', {
        headers: {},
      });
      setFiles(data.files || []);
      setSelectedFile('');
      setFileContent('');
      setStatus('ready');
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  }, [request]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  const handleUpload = async () => {
    if (!uploadFile) return;
    setStatus('saving');
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      const response = await fetch(`${API_BASE}/api/admin/contents/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.message || 'Upload failed');
      }
      setUploadFile(null);
      await loadItems();
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  const handleOpenFile = async (fileName) => {
    setStatus('loading');
    setError('');
    try {
      const data = await request(`/api/admin/contents/file?path=${encodeURIComponent(fileName)}`);
      setSelectedFile(fileName);
      setFileContent(JSON.stringify(data.content, null, 2));
      setStatus('ready');
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  const handleSaveFile = async () => {
    if (!selectedFile) return;
    setStatus('saving');
    setError('');
    try {
      const parsed = JSON.parse(fileContent);
      await request('/api/admin/contents/file', {
        method: 'PUT',
        body: JSON.stringify({ path: selectedFile, content: parsed }),
      });
      setStatus('ready');
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  return (
    <section className="panel">
      <h2>Content Manager</h2>
      <div className="content-grid">
        <div className="card-section">
          <div className="section-header">
            <div>
              <div className="section-title">Collection: main-book</div>
              <div className="muted small">Uploads are stored in main-book</div>
            </div>
          </div>
          {status === 'loading' && <p className="muted">Loading…</p>}
          {error && <p className="error">{error}</p>}
          <div className="list">
            {files.map((file) => (
              <button key={file} className={`list-item ${file === selectedFile ? 'active' : ''}`} onClick={() => handleOpenFile(file)}>
                📄 {file}
              </button>
            ))}
            {!files.length && status === 'ready' && (
              <div className="muted">No files yet</div>
            )}
          </div>
        </div>
        <div className="card-section">
          <div className="section-title">Upload JSON</div>
          <input type="file" accept=".json,application/json" onChange={(event) => setUploadFile(event.target.files[0] || null)} />
          <button className="primary" onClick={handleUpload} disabled={!uploadFile}>Upload to main-book</button>
        </div>
        <div className="card-section">
          <div className="section-title">Edit JSON</div>
          {selectedFile ? (
            <>
              <div className="muted small">Editing {selectedFile}</div>
              <textarea value={fileContent} onChange={(event) => setFileContent(event.target.value)} rows={18} />
              <button className="primary" onClick={handleSaveFile}>Save</button>
            </>
          ) : (
            <div className="muted">Select a JSON file to edit</div>
          )}
        </div>
      </div>
    </section>
  );
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
        <Route
          path="/admin/users"
          element={
            <PageShell>
              <UsersPage />
            </PageShell>
          }
        />
        <Route
          path="/admin/contents"
          element={
            <PageShell>
              <ContentsPage />
            </PageShell>
          }
        />
        <Route path="*" element={<Navigate to="/admin/users" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
