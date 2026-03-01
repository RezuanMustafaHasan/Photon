const cors = require('cors');
const express = require('express');
const fs = require('fs/promises');
const path = require('path');
const mongoose = require('mongoose');
const multer = require('multer');

const app = express();
const PORT = process.env.PORT || 5050;
const USERS_FILE = path.join(__dirname, 'db', 'users.json');
const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/hsc_physics_db';
const MAIN_COLLECTION = 'main-book';
const MAIN_DOC_ID = 'main-book';

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 15 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (path.extname(file.originalname).toLowerCase() !== '.json') {
      return cb(new Error('Only .json files are allowed'));
    }
    cb(null, true);
  },
});

app.use(cors());
app.use(express.json({ limit: '10mb' }));

let connectPromise;

const connectMongo = () => {
  if (!connectPromise) {
    connectPromise = mongoose.connect(MONGODB_URI);
  }
  return connectPromise;
};

const getDb = async () => {
  await connectMongo();
  return mongoose.connection.db;
};

const ensureDirectory = async (dirPath) => {
  await fs.mkdir(dirPath, { recursive: true });
};

const ensureSeedFiles = async () => {
  await ensureDirectory(path.dirname(USERS_FILE));
  try {
    await fs.access(USERS_FILE);
  } catch (error) {
    const seedUsers = [
      { id: 'u-001', name: 'Admin Demo', email: 'admin@example.com', role: 'admin' },
      { id: 'u-002', name: 'Student Demo', email: 'student@example.com', role: 'student' },
    ];
    await fs.writeFile(USERS_FILE, JSON.stringify(seedUsers, null, 2), 'utf8');
  }
};

const getMainCollection = async () => {
  const db = await getDb();
  return db.collection(MAIN_COLLECTION);
};

const ensureMainDoc = async () => {
  const collection = await getMainCollection();
  await collection.updateOne(
    { _id: MAIN_DOC_ID },
    { $setOnInsert: { _id: MAIN_DOC_ID, items: [] } },
    { upsert: true },
  );
  return collection;
};

const loadMainItems = async () => {
  const collection = await ensureMainDoc();
  const doc = await collection.findOne({ _id: MAIN_DOC_ID });
  return Array.isArray(doc?.items) ? doc.items : [];
};

const writeMainItems = async (items) => {
  const collection = await ensureMainDoc();
  await collection.updateOne(
    { _id: MAIN_DOC_ID },
    { $set: { items } },
  );
};

const normalizeFileName = (input) => {
  if (!input || typeof input !== 'string') {
    throw new Error('File name is required');
  }
  const fileName = path.basename(input);
  if (!fileName || path.extname(fileName).toLowerCase() !== '.json') {
    throw new Error('Only .json files are allowed');
  }
  return fileName;
};

app.get('/api/admin/users', async (req, res) => {
  try {
    const data = await fs.readFile(USERS_FILE, 'utf8');
    const users = JSON.parse(data);
    res.json({ users });
  } catch (error) {
    res.status(500).json({ message: 'Failed to load users' });
  }
});

app.get('/api/admin/contents/directories', async (req, res) => {
  try {
    res.json({ directories: [] });
  } catch (error) {
    res.status(500).json({ message: 'Failed to load directories' });
  }
});

app.get('/api/admin/contents/list', async (req, res) => {
  try {
    const items = await loadMainItems();
    const files = items.map((item) => item.name).filter(Boolean).sort();
    res.json({ directories: [], files });
  } catch (error) {
    res.status(400).json({ message: 'Failed to list directory' });
  }
});

app.post('/api/admin/contents/directory', async (req, res) => {
  try {
    await ensureMainDoc();
    res.json({ message: 'Collection ready' });
  } catch (error) {
    res.status(400).json({ message: 'Failed to prepare collection' });
  }
});

app.post('/api/admin/contents/upload', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ message: 'No file provided' });
    }
    const safeName = normalizeFileName(req.file.originalname);
    let content;
    try {
      content = JSON.parse(req.file.buffer.toString('utf8'));
    } catch (parseError) {
      return res.status(400).json({ message: 'Invalid JSON file' });
    }
    const items = await loadMainItems();
    const existingIndex = items.findIndex((item) => item.name === safeName);
    const now = new Date();
    if (existingIndex >= 0) {
      items[existingIndex] = { ...items[existingIndex], name: safeName, content, updatedAt: now };
    } else {
      items.push({ name: safeName, content, createdAt: now, updatedAt: now });
    }
    await writeMainItems(items);
    res.json({ message: 'File uploaded', fileName: safeName });
  } catch (error) {
    res.status(400).json({ message: 'Failed to upload file' });
  }
});

app.get('/api/admin/contents/file', async (req, res) => {
  try {
    const fileName = normalizeFileName(req.query.path || '');
    const items = await loadMainItems();
    const item = items.find((entry) => entry.name === fileName);
    if (!item) {
      return res.status(404).json({ message: 'File not found' });
    }
    res.json({ content: item.content });
  } catch (error) {
    res.status(400).json({ message: 'Failed to read file' });
  }
});

app.put('/api/admin/contents/file', async (req, res) => {
  try {
    const fileName = normalizeFileName(req.body.path || '');
    const content = req.body.content;
    let json;
    if (typeof content === 'string') {
      json = JSON.parse(content);
    } else {
      json = content;
    }
    const items = await loadMainItems();
    const existingIndex = items.findIndex((item) => item.name === fileName);
    if (existingIndex < 0) {
      return res.status(404).json({ message: 'File not found' });
    }
    items[existingIndex] = { ...items[existingIndex], name: fileName, content: json, updatedAt: new Date() };
    await writeMainItems(items);
    res.json({ message: 'File updated' });
  } catch (error) {
    res.status(400).json({ message: 'Failed to update file' });
  }
});

app.use((err, req, res, next) => {
  if (err) {
    res.status(400).json({ message: err.message || 'Request failed' });
    return;
  }
  next();
});

ensureSeedFiles()
  .then(connectMongo)
  .then(() => {
    app.listen(PORT, () => {
      console.log(`Admin backend running on http://localhost:${PORT}`);
    });
  })
  .catch((error) => {
    console.error('Failed to start admin backend:', error.message);
    process.exit(1);
  });
