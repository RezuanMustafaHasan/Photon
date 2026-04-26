import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useNavigate, useLocation } from 'react-router-dom';
import './App.css';

const API_BASE = import.meta.env.VITE_ADMIN_API_URL || 'http://localhost:5050';
const ADMIN_TOKEN_KEY = 'photon_admin_token';
const ADMIN_USER_KEY = 'photon_admin_user';

const AdminAuthContext = createContext(null);

const parseStoredUser = (rawUser) => {
  if (!rawUser) {
    return null;
  }

  try {
    return JSON.parse(rawUser);
  } catch {
    return null;
  }
};

const readStoredSession = () => {
  const localToken = localStorage.getItem(ADMIN_TOKEN_KEY);
  const sessionToken = sessionStorage.getItem(ADMIN_TOKEN_KEY);
  const token = localToken || sessionToken || null;
  const userRaw = localToken
    ? localStorage.getItem(ADMIN_USER_KEY)
    : sessionStorage.getItem(ADMIN_USER_KEY);

  return {
    token,
    user: parseStoredUser(userRaw),
    remember: Boolean(localToken),
  };
};

const normalizeUserRole = (role) => String(role || '').trim().toLowerCase();

const getDefaultAdminPath = (user) => {
  return normalizeUserRole(user?.role) === 'admin' ? '/admin/users' : '/admin/contents';
};

const AdminAuthProvider = ({ children }) => {
  const initial = readStoredSession();
  const [token, setToken] = useState(initial.token);
  const [user, setUser] = useState(initial.user);
  const [isHydrating, setIsHydrating] = useState(Boolean(initial.token));

  const clearStoredSession = useCallback(() => {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    localStorage.removeItem(ADMIN_USER_KEY);
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    sessionStorage.removeItem(ADMIN_USER_KEY);
  }, []);

  const persistSession = useCallback((nextToken, nextUser, remember) => {
    clearStoredSession();
    const storage = remember ? localStorage : sessionStorage;
    storage.setItem(ADMIN_TOKEN_KEY, nextToken);
    storage.setItem(ADMIN_USER_KEY, JSON.stringify(nextUser));
  }, [clearStoredSession]);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setIsHydrating(false);
    clearStoredSession();
  }, [clearStoredSession]);

  const login = useCallback(async ({ email, password, remember }) => {
    const response = await fetch(`${API_BASE}/api/admin/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.message || 'Login failed');
    }

    setToken(data.token || null);
    setUser(data.user || null);
    setIsHydrating(false);
    persistSession(data.token, data.user, remember);

    return data.user;
  }, [persistSession]);

  useEffect(() => {
    let mounted = true;

    const hydrateSession = async () => {
      if (!token) {
        setIsHydrating(false);
        return;
      }

      try {
        const response = await fetch(`${API_BASE}/api/admin/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await response.json().catch(() => ({}));

        if (!mounted) {
          return;
        }

        if (!response.ok) {
          logout();
          return;
        }

        setUser(data.user || null);
      } catch {
        if (mounted) {
          logout();
        }
      } finally {
        if (mounted) {
          setIsHydrating(false);
        }
      }
    };

    hydrateSession();

    return () => {
      mounted = false;
    };
  }, [token, logout]);

  const value = useMemo(
    () => ({
      token,
      user,
      isHydrating,
      isAuthenticated: Boolean(token),
      login,
      logout,
    }),
    [token, user, isHydrating, login, logout],
  );

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>;
};

const useAdminAuth = () => {
  const context = useContext(AdminAuthContext);
  if (!context) {
    throw new Error('useAdminAuth must be used within AdminAuthProvider');
  }
  return context;
};

const useAdminApi = () => {
  const { token, logout } = useAdminAuth();

  const request = useCallback(async (path, options = {}) => {
    const headers = new Headers(options.headers || {});

    if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      if (response.status === 401) {
        logout();
      }
      throw new Error(data.message || 'Request failed');
    }

    return data;
  }, [token, logout]);

  return { request };
};

const normalizeTopicList = (value) => {
  if (!Array.isArray(value)) {
    return [];
  }

  const seen = new Set();
  return value
    .map((item) => String(item || '').trim())
    .filter((item) => {
      if (!item) {
        return false;
      }

      const normalized = item.toLowerCase();
      if (seen.has(normalized)) {
        return false;
      }

      seen.add(normalized);
      return true;
    });
};

const addTopicToList = (topicInput, currentTopics, setTopics, setTopicInput) => {
  const cleanTopic = topicInput.trim();
  if (!cleanTopic) {
    return;
  }

  const alreadyExists = currentTopics.some((topic) => topic.toLowerCase() === cleanTopic.toLowerCase());
  if (!alreadyExists) {
    setTopics((previous) => [...previous, cleanTopic]);
  }

  setTopicInput('');
};

const PageShell = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAdminAuth();
  const role = normalizeUserRole(user?.role);
  const canViewUsers = role === 'admin';
  const canManageContent = role === 'admin' || role === 'editor';
  const isUsers = location.pathname.includes('/admin/users');
  const isContents = location.pathname.includes('/admin/contents');
  const isImages = location.pathname.includes('/admin/images');

  const handleLogout = () => {
    logout();
    navigate('/admin/login', { replace: true });
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <div className="app-title">Photon Admin</div>
          <div className="app-subtitle">Manage users, content, and lesson images</div>
        </div>
        <div className="app-header-actions">
          <nav className="nav-links">
            {canViewUsers && (
              <button className={isUsers ? 'active' : ''} onClick={() => navigate('/admin/users')}>Users</button>
            )}
            {canManageContent && (
              <button className={isContents ? 'active' : ''} onClick={() => navigate('/admin/contents')}>Contents</button>
            )}
            {canManageContent && (
              <button className={isImages ? 'active' : ''} onClick={() => navigate('/admin/images')}>Lesson Images</button>
            )}
          </nav>
          <div className="admin-user-controls">
            <div className="user-pill">
              <span className="user-pill-name">{user?.name || 'Admin User'}</span>
              <span className="user-pill-role">{user?.role || 'admin'}</span>
            </div>
            <button type="button" className="secondary" onClick={handleLogout}>Sign Out</button>
          </div>
        </div>
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
      const data = await request('/api/admin/contents/list');
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
      await request('/api/admin/contents/upload', {
        method: 'POST',
        body: formData,
      });
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
              <div className="section-title">Collection: main_book</div>
              <div className="muted small">Uploads are stored in main_book</div>
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
          <button className="primary" onClick={handleUpload} disabled={!uploadFile}>Upload to main_book</button>
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

const ImagesPage = () => {
  const { request } = useAdminApi();
  const [chapters, setChapters] = useState([]);
  const [selectedChapterId, setSelectedChapterId] = useState('');
  const [lessons, setLessons] = useState([]);
  const [selectedLesson, setSelectedLesson] = useState('');
  const [lessonImages, setLessonImages] = useState([]);
  const [selectedImageIndex, setSelectedImageIndex] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [description, setDescription] = useState('');
  const [topicInput, setTopicInput] = useState('');
  const [topics, setTopics] = useState([]);
  const [editImageFile, setEditImageFile] = useState(null);
  const [editDescription, setEditDescription] = useState('');
  const [editTopicInput, setEditTopicInput] = useState('');
  const [editTopics, setEditTopics] = useState([]);
  const [chaptersStatus, setChaptersStatus] = useState('idle');
  const [lessonsStatus, setLessonsStatus] = useState('idle');
  const [imagesStatus, setImagesStatus] = useState('idle');
  const [actionStatus, setActionStatus] = useState('idle');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [activeImageUrl, setActiveImageUrl] = useState('');
  const selectedImage = lessonImages.find((image) => image.index === selectedImageIndex) || null;
  const isActionBusy = actionStatus === 'saving' || actionStatus === 'deleting';

  const loadLessonImages = useCallback(async (chapterId = selectedChapterId, lessonName = selectedLesson, preferredIndex = null) => {
    if (!chapterId || !lessonName) {
      setLessonImages([]);
      setSelectedImageIndex(null);
      setImagesStatus('idle');
      return [];
    }

    setImagesStatus('loading');
    setError('');

    try {
      const data = await request(
        `/api/admin/images/lesson?chapterId=${encodeURIComponent(chapterId)}&lessonName=${encodeURIComponent(lessonName)}`,
      );
      const images = Array.isArray(data.images) ? data.images : [];
      setLessonImages(images);
      setSelectedImageIndex((previousIndex) => {
        const targetIndex = preferredIndex ?? previousIndex;
        return images.some((image) => image.index === targetIndex) ? targetIndex : (images[0]?.index ?? null);
      });
      setImagesStatus('ready');
      return images;
    } catch (err) {
      setLessonImages([]);
      setSelectedImageIndex(null);
      setImagesStatus('error');
      setError(err.message);
      return [];
    }
  }, [request, selectedChapterId, selectedLesson]);

  useEffect(() => {
    let mounted = true;
    const loadChapters = async () => {
      setChaptersStatus('loading');
      setError('');
      try {
        const data = await request('/api/admin/images/chapters');
        if (!mounted) {
          return;
        }
        setChapters(data.chapters || []);
        setChaptersStatus('ready');
      } catch (err) {
        if (!mounted) {
          return;
        }
        setChaptersStatus('error');
        setError(err.message);
      }
    };

    loadChapters();

    return () => {
      mounted = false;
    };
  }, [request]);

  useEffect(() => {
    let mounted = true;
    const loadLessons = async () => {
      if (!selectedChapterId) {
        setLessons([]);
        setSelectedLesson('');
        setLessonImages([]);
        setSelectedImageIndex(null);
        setLessonsStatus('idle');
        setImagesStatus('idle');
        return;
      }

      setLessonsStatus('loading');
      setError('');
      setSuccess('');
      setActiveImageUrl('');
      try {
        const data = await request(`/api/admin/images/lessons?chapterId=${encodeURIComponent(selectedChapterId)}`);
        if (!mounted) {
          return;
        }
        setLessons(data.lessons || []);
        setSelectedLesson('');
        setLessonImages([]);
        setSelectedImageIndex(null);
        setLessonsStatus('ready');
        setImagesStatus('idle');
      } catch (err) {
        if (!mounted) {
          return;
        }
        setLessons([]);
        setLessonImages([]);
        setSelectedImageIndex(null);
        setLessonsStatus('error');
        setError(err.message);
      }
    };

    loadLessons();

    return () => {
      mounted = false;
    };
  }, [request, selectedChapterId]);

  useEffect(() => {
    if (!selectedLesson) {
      setLessonImages([]);
      setSelectedImageIndex(null);
      setImagesStatus('idle');
      return;
    }

    loadLessonImages(selectedChapterId, selectedLesson);
  }, [loadLessonImages, selectedChapterId, selectedLesson]);

  useEffect(() => {
    setImageFile(null);
    setDescription('');
    setTopicInput('');
    setTopics([]);
  }, [selectedChapterId, selectedLesson]);

  useEffect(() => {
    if (!selectedImage) {
      setEditImageFile(null);
      setEditDescription('');
      setEditTopicInput('');
      setEditTopics([]);
      return;
    }

    setEditImageFile(null);
    setEditDescription(selectedImage.description || '');
    setEditTopicInput('');
    setEditTopics(normalizeTopicList(selectedImage.topic));
  }, [selectedImage]);

  const handleUpload = async () => {
    if (!selectedChapterId || !selectedLesson || !imageFile) {
      setError('Select chapter, lesson, and image file first');
      return;
    }
    if (!description.trim()) {
      setError('Image description is required');
      return;
    }
    if (!topics.length) {
      setError('Add at least one topic');
      return;
    }

    setActionStatus('saving');
    setError('');
    setSuccess('');
    try {
      const formData = new FormData();
      formData.append('image', imageFile);
      formData.append('chapterId', selectedChapterId);
      formData.append('lessonName', selectedLesson);
      formData.append('description', description.trim());
      formData.append('topics', JSON.stringify(topics));

      const data = await request('/api/admin/images/upload', {
        method: 'POST',
        body: formData,
      });

      const images = await loadLessonImages(selectedChapterId, selectedLesson);
      setSuccess(data.message || 'Image uploaded and lesson updated');
      setActiveImageUrl(data?.image?.imageURL || images[images.length - 1]?.imageURL || '');
      setSelectedImageIndex(images[images.length - 1]?.index ?? null);
      setImageFile(null);
      setDescription('');
      setTopicInput('');
      setTopics([]);
      setActionStatus('ready');
    } catch (err) {
      setError(err.message);
      setActionStatus('error');
    }
  };

  const handleUpdate = async () => {
    if (!selectedChapterId || !selectedLesson || selectedImageIndex === null) {
      setError('Select an image to update');
      return;
    }
    if (!editDescription.trim()) {
      setError('Image description is required');
      return;
    }
    if (!editTopics.length) {
      setError('Add at least one topic');
      return;
    }

    setActionStatus('saving');
    setError('');
    setSuccess('');

    try {
      const formData = new FormData();
      if (editImageFile) {
        formData.append('image', editImageFile);
      }
      formData.append('chapterId', selectedChapterId);
      formData.append('lessonName', selectedLesson);
      formData.append('imageIndex', String(selectedImageIndex));
      formData.append('description', editDescription.trim());
      formData.append('topics', JSON.stringify(editTopics));

      const data = await request('/api/admin/images/item', {
        method: 'PUT',
        body: formData,
      });

      await loadLessonImages(selectedChapterId, selectedLesson, selectedImageIndex);
      setSuccess(data.message || 'Image updated');
      setActiveImageUrl(data?.image?.imageURL || selectedImage?.imageURL || '');
      setEditImageFile(null);
      setActionStatus('ready');
    } catch (err) {
      setError(err.message);
      setActionStatus('error');
    }
  };

  const handleDelete = async (imageIndex = selectedImageIndex) => {
    if (!selectedChapterId || !selectedLesson || imageIndex === null) {
      setError('Select an image to delete');
      return;
    }

    const confirmed = window.confirm('Delete this image from the lesson?');
    if (!confirmed) {
      return;
    }

    setActionStatus('deleting');
    setError('');
    setSuccess('');

    try {
      const data = await request(
        `/api/admin/images/item?chapterId=${encodeURIComponent(selectedChapterId)}&lessonName=${encodeURIComponent(selectedLesson)}&imageIndex=${encodeURIComponent(String(imageIndex))}`,
        { method: 'DELETE' },
      );

      const images = await loadLessonImages(selectedChapterId, selectedLesson);
      const fallbackImage = images[Math.min(imageIndex, Math.max(images.length - 1, 0))] || null;
      setSelectedImageIndex(fallbackImage?.index ?? null);
      setSuccess(data.warning || data.message || 'Image deleted');
      setActiveImageUrl('');
      setActionStatus('ready');
    } catch (err) {
      setError(err.message);
      setActionStatus('error');
    }
  };

  return (
    <section className="panel">
      <h2>Lesson Image Manager</h2>
      {(error || success || activeImageUrl) && (
        <div className="feedback-stack">
          {error && <div className="error">{error}</div>}
          {success && <div className="success">{success}</div>}
          {activeImageUrl && (
            <a className="image-link" href={activeImageUrl} target="_blank" rel="noreferrer">
              Open current image URL
            </a>
          )}
        </div>
      )}

      <div className="content-grid">
        <div className="card-section">
          <div className="section-title">1. Select chapter</div>
          <select
            value={selectedChapterId}
            onChange={(event) => {
              setSelectedChapterId(event.target.value);
              setError('');
              setSuccess('');
              setActiveImageUrl('');
            }}
          >
            <option value="">Choose a chapter</option>
            {chapters.map((chapter) => (
              <option key={chapter.id} value={chapter.id}>{chapter.name}</option>
            ))}
          </select>
          {chaptersStatus === 'loading' && <div className="muted">Loading chapter data...</div>}
        </div>

        <div className="card-section">
          <div className="section-title">2. Select lesson</div>
          <div className="list">
            {lessons.map((lesson) => (
              <button
                key={lesson}
                className={`list-item ${selectedLesson === lesson ? 'active' : ''}`}
                onClick={() => {
                  setSelectedLesson(lesson);
                  setError('');
                  setSuccess('');
                  setActiveImageUrl('');
                }}
              >
                {lesson}
              </button>
            ))}
            {!lessons.length && selectedChapterId && lessonsStatus !== 'loading' && (
              <div className="muted">No lessons found for this chapter</div>
            )}
            {!selectedChapterId && (
              <div className="muted">Choose a chapter to load lessons</div>
            )}
          </div>
          {lessonsStatus === 'loading' && <div className="muted small">Loading lessons...</div>}
        </div>

        <div className="card-section wide-section">
          <div className="section-header">
            <div>
              <div className="section-title">3. Existing lesson images</div>
              <div className="muted small">
                {selectedLesson ? `Viewing images under ${selectedLesson}` : 'Choose a lesson to inspect its images array'}
              </div>
            </div>
            {imagesStatus === 'loading' && <div className="muted small">Loading images...</div>}
          </div>

          {!selectedLesson && (
            <div className="muted">Select a lesson to view <code>{'chapter -> lessons -> lesson -> images'}</code>.</div>
          )}

          {selectedLesson && !lessonImages.length && imagesStatus === 'ready' && (
            <div className="muted">No uploaded images found under this lesson yet.</div>
          )}

          {!!lessonImages.length && (
            <div className="image-gallery">
              {lessonImages.map((image) => (
                <article
                  key={`${image.index}-${image.imageURL}`}
                  className={`image-card ${selectedImageIndex === image.index ? 'active' : ''}`}
                >
                  <button
                    type="button"
                    className="image-preview-button"
                    onClick={() => setSelectedImageIndex(image.index)}
                  >
                    <img
                      src={image.imageURL}
                      alt={image.description || `Lesson image ${image.index + 1}`}
                    />
                  </button>

                  <div className="image-card-body">
                    <div className="image-card-title">Image {image.index + 1}</div>
                    <div className="image-card-description">{image.description || 'No description saved.'}</div>

                    <div className="topic-list">
                      {normalizeTopicList(image.topic).map((topic) => (
                        <span key={`${image.index}-${topic}`} className="topic-chip static">{topic}</span>
                      ))}
                      {!normalizeTopicList(image.topic).length && (
                        <div className="muted small">No topics saved</div>
                      )}
                    </div>

                    <div className="action-row compact">
                      <button type="button" className="secondary" onClick={() => setSelectedImageIndex(image.index)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        className="danger ghost"
                        onClick={() => handleDelete(image.index)}
                        disabled={isActionBusy}
                      >
                        Delete
                      </button>
                      <a className="image-link" href={image.imageURL} target="_blank" rel="noreferrer">
                        Open
                      </a>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="card-section">
          <div className="section-title">4. Upload new image</div>
          <input type="file" accept="image/*" onChange={(event) => setImageFile(event.target.files[0] || null)} />
          <textarea
            rows={5}
            placeholder="Image description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />

          <div className="topic-editor">
            <input
              type="text"
              placeholder="Add topic"
              value={topicInput}
              onChange={(event) => setTopicInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  addTopicToList(topicInput, topics, setTopics, setTopicInput);
                }
              }}
            />
            <button type="button" onClick={() => addTopicToList(topicInput, topics, setTopics, setTopicInput)}>Add Topic</button>
          </div>

          <div className="topic-list">
            {topics.map((topic) => (
              <button key={topic} type="button" className="topic-chip" onClick={() => setTopics((previous) => previous.filter((item) => item !== topic))}>
                {topic} x
              </button>
            ))}
            {!topics.length && <div className="muted small">No topics added yet</div>}
          </div>

          <button className="primary" onClick={handleUpload} disabled={isActionBusy}>
            {actionStatus === 'saving' ? 'Uploading...' : 'Upload and Save'}
          </button>
          <div className="muted small">Select a chapter and lesson before uploading.</div>
        </div>

        <div className="card-section wide-section">
          <div className="section-title">5. Update or delete selected image</div>
          {!selectedImage && (
            <div className="muted">Pick an image from the lesson gallery to edit its file, description, or topics.</div>
          )}

          {selectedImage && (
            <>
              <div className="selected-image-panel">
                <img
                  className="selected-image-preview"
                  src={selectedImage.imageURL}
                  alt={selectedImage.description || `Lesson image ${selectedImage.index + 1}`}
                />
                <div className="selected-image-meta">
                  <div className="muted small">Currently editing image {selectedImage.index + 1}</div>
                  <a className="image-link" href={selectedImage.imageURL} target="_blank" rel="noreferrer">
                    Open current image
                  </a>
                </div>
              </div>

              <input type="file" accept="image/*" onChange={(event) => setEditImageFile(event.target.files[0] || null)} />
              <div className="muted small">Upload a new file only if you want to replace the current image.</div>

              <textarea
                rows={5}
                placeholder="Image description"
                value={editDescription}
                onChange={(event) => setEditDescription(event.target.value)}
              />

              <div className="topic-editor">
                <input
                  type="text"
                  placeholder="Add topic"
                  value={editTopicInput}
                  onChange={(event) => setEditTopicInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      addTopicToList(editTopicInput, editTopics, setEditTopics, setEditTopicInput);
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={() => addTopicToList(editTopicInput, editTopics, setEditTopics, setEditTopicInput)}
                >
                  Add Topic
                </button>
              </div>

              <div className="topic-list">
                {editTopics.map((topic) => (
                  <button
                    key={topic}
                    type="button"
                    className="topic-chip"
                    onClick={() => setEditTopics((previous) => previous.filter((item) => item !== topic))}
                  >
                    {topic} x
                  </button>
                ))}
                {!editTopics.length && <div className="muted small">No topics added yet</div>}
              </div>

              <div className="action-row">
                <button className="primary" onClick={handleUpdate} disabled={isActionBusy}>
                  {actionStatus === 'saving' ? 'Saving...' : 'Save Changes'}
                </button>
                <button className="danger" onClick={() => handleDelete(selectedImage.index)} disabled={isActionBusy}>
                  {actionStatus === 'deleting' ? 'Deleting...' : 'Delete Image'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
};

const RequireAuth = ({ children, roles = [] }) => {
  const location = useLocation();
  const { isHydrating, isAuthenticated, user } = useAdminAuth();

  if (isHydrating) {
    return (
      <div className="auth-screen">
        <section className="auth-card">
          <h2>Loading Admin Session</h2>
          <p className="muted">Checking your credentials...</p>
        </section>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/admin/login" replace state={{ from: location.pathname }} />;
  }

  const allowedRoles = roles.map(normalizeUserRole);
  if (allowedRoles.length && !allowedRoles.includes(normalizeUserRole(user?.role))) {
    return <Navigate to={getDefaultAdminPath(user)} replace />;
  }

  return children;
};

const LoginPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, isHydrating, user } = useAdminAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isHydrating && isAuthenticated) {
      navigate(getDefaultAdminPath(user), { replace: true });
    }
  }, [isAuthenticated, isHydrating, navigate, user]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setStatus('submitting');
    setError('');

    try {
      const loggedInUser = await login({ email, password, remember });
      const fromPath = typeof location.state?.from === 'string' ? location.state.from : '';
      const hasAdminPrefix = fromPath === '/admin' || fromPath.startsWith('/admin/');

      let nextPath = hasAdminPrefix ? fromPath : getDefaultAdminPath(loggedInUser);
      if (normalizeUserRole(loggedInUser?.role) !== 'admin' && nextPath === '/admin/users') {
        nextPath = getDefaultAdminPath(loggedInUser);
      }

      navigate(nextPath, { replace: true });
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  };

  if (isHydrating) {
    return (
      <div className="auth-screen">
        <section className="auth-card">
          <h2>Loading Admin Session</h2>
          <p className="muted">Please wait...</p>
        </section>
      </div>
    );
  }

  return (
    <div className="auth-screen">
      <section className="auth-card">
        <h1>Photon Admin</h1>
        <p className="muted">Sign in to access the admin panel.</p>
        {error && <p className="error">{error}</p>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <label htmlFor="admin-email">Email</label>
          <input
            id="admin-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />

          <label htmlFor="admin-password">Password</label>
          <input
            id="admin-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />

          <label className="remember-row" htmlFor="remember-admin-session">
            <input
              id="remember-admin-session"
              type="checkbox"
              checked={remember}
              onChange={(event) => setRemember(event.target.checked)}
            />
            <span>Keep me signed in</span>
          </label>

          <button className="primary" type="submit" disabled={status === 'submitting'}>
            {status === 'submitting' ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </section>
    </div>
  );
};

const AdminHomeRedirect = () => {
  const { user } = useAdminAuth();
  return <Navigate to={getDefaultAdminPath(user)} replace />;
};

function App() {
  return (
    <AdminAuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/admin/login" element={<LoginPage />} />
          <Route
            path="/admin"
            element={
              <RequireAuth>
                <AdminHomeRedirect />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/users"
            element={
              <RequireAuth roles={['admin']}>
                <PageShell>
                  <UsersPage />
                </PageShell>
              </RequireAuth>
            }
          />
          <Route
            path="/admin/contents"
            element={
              <RequireAuth roles={['admin', 'editor']}>
                <PageShell>
                  <ContentsPage />
                </PageShell>
              </RequireAuth>
            }
          />
          <Route
            path="/admin/images"
            element={
              <RequireAuth roles={['admin', 'editor']}>
                <PageShell>
                  <ImagesPage />
                </PageShell>
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </BrowserRouter>
    </AdminAuthProvider>
  );
}

export default App;
