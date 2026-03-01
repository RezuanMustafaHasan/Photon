import express from 'express';
import mongoose from 'mongoose';
import cors from 'cors';
import dotenv from 'dotenv';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;
const JWT_SECRET = process.env.JWT_SECRET || 'dev_secret_change_me';
const FASTAPI_CHAT_URL = process.env.FASTAPI_CHAT_URL || 'http://localhost:8000/chat';
const MAIN_COLLECTION = 'main_book';
const MAIN_DOC_ID = 'main_book';

app.use(cors({ origin: true }));
app.use(express.json());

app.get('/', (req, res) => {
  res.send('API is running...');
});

app.post('/api/chat', async (req, res) => {
  const message = typeof req.body?.message === 'string' ? req.body.message.trim() : '';
  const system = typeof req.body?.system === 'string' ? req.body.system : undefined;

  if (!message) {
    res.status(400).json({ message: 'message is required' });
    return;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  try {
    const upstream = await fetch(FASTAPI_CHAT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(system ? { message, system } : { message }),
      signal: controller.signal,
    });

    const data = await upstream.json().catch(() => null);
    if (!upstream.ok) {
      res.status(502).json({ message: data?.detail || data?.message || 'Upstream error' });
      return;
    }

    const responseText = typeof data?.response === 'string' ? data.response : '';
    res.json({ response: responseText });
  } catch {
    res.status(502).json({ message: 'FastAPI is unreachable' });
  } finally {
    clearTimeout(timeoutId);
  }
});

mongoose.connect(process.env.MONGODB_URI || 'mongodb://localhost:27017/hsc_physics_db')
  .then(() => console.log('MongoDB Connected'))
  .catch(err => console.error('MongoDB connection error:', err));

const getDb = async () => {
  if (mongoose.connection.readyState !== 1) {
    await mongoose.connection.asPromise();
  }
  return mongoose.connection.db;
};

const normalizeTitle = (value) => String(value || '').trim().toLowerCase();

const userSchema = new mongoose.Schema(
  {
    name: { type: String, required: true, trim: true },
    email: { type: String, required: true, unique: true, lowercase: true, trim: true },
    passwordHash: { type: String, required: true },
  },
  { timestamps: true },
);

const User = mongoose.models.User || mongoose.model('User', userSchema);

const createAuthPayload = (user) => {
  const token = jwt.sign({ sub: user._id.toString() }, JWT_SECRET, { expiresIn: '7d' });
  return {
    token,
    user: {
      id: user._id.toString(),
      name: user.name,
      email: user.email,
    },
  };
};

const authMiddleware = (req, res, next) => {
  const header = req.headers.authorization || '';
  const [type, token] = header.split(' ');
  if (type !== 'Bearer' || !token) {
    res.status(401).json({ message: 'Unauthorized.' });
    return;
  }
  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    req.userId = decoded.sub;
    next();
  } catch {
    res.status(401).json({ message: 'Unauthorized.' });
  }
};

app.post('/api/auth/signup', async (req, res) => {
  try {
    const name = String(req.body?.name || '').trim();
    const email = String(req.body?.email || '').trim().toLowerCase();
    const password = String(req.body?.password || '');

    if (!name || name.length < 2) {
      res.status(400).json({ message: 'Full name is required.' });
      return;
    }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      res.status(400).json({ message: 'Enter a valid email address.' });
      return;
    }
    if (!password || password.length < 8) {
      res.status(400).json({ message: 'Password must be at least 8 characters.' });
      return;
    }

    const existing = await User.findOne({ email }).lean();
    if (existing) {
      res.status(409).json({ message: 'An account with that email already exists.' });
      return;
    }

    const passwordHash = await bcrypt.hash(password, 10);
    const user = await User.create({ name, email, passwordHash });
    res.status(201).json(createAuthPayload(user));
  } catch (err) {
    res.status(500).json({ message: 'Server error.' });
  }
});

app.post('/api/auth/login', async (req, res) => {
  try {
    const email = String(req.body?.email || '').trim().toLowerCase();
    const password = String(req.body?.password || '');

    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      res.status(400).json({ message: 'Enter a valid email address.' });
      return;
    }
    if (!password) {
      res.status(400).json({ message: 'Password is required.' });
      return;
    }

    const user = await User.findOne({ email });
    if (!user) {
      res.status(401).json({ message: 'Invalid email or password.' });
      return;
    }

    const ok = await bcrypt.compare(password, user.passwordHash);
    if (!ok) {
      res.status(401).json({ message: 'Invalid email or password.' });
      return;
    }

    res.json(createAuthPayload(user));
  } catch {
    res.status(500).json({ message: 'Server error.' });
  }
});

app.get('/api/auth/me', authMiddleware, async (req, res) => {
  try {
    const user = await User.findById(req.userId).lean();
    if (!user) {
      res.status(404).json({ message: 'User not found.' });
      return;
    }
    res.json({ id: user._id.toString(), name: user.name, email: user.email });
  } catch {
    res.status(500).json({ message: 'Server error.' });
  }
});

app.get('/api/chapters', async (req, res) => {
  try {
    const db = await getDb();
    const doc = await db.collection(MAIN_COLLECTION).findOne({ _id: MAIN_DOC_ID });
    const items = Array.isArray(doc?.items) ? doc.items : [];
    const chapters = items.map((item) => {
      const source = item?.content && typeof item.content === 'object' ? item.content : item;
      const chapterName = source?.chapter_name || item?.name || '';
      const chapterNameBn = source?.chapter_name_bn || source?.chapter_name || chapterName;
      return {
        chapter_name: chapterName,
        chapter_name_bn: chapterNameBn,
      };
    }).filter((chapter) => chapter.chapter_name_bn);
    res.json({ chapters });
  } catch (error) {
    res.status(500).json({ message: 'Failed to load chapters' });
  }
});

app.get('/api/chapters/:chapterTitle/lessons', async (req, res) => {
  try {
    const title = req.params.chapterTitle;
    if (!title) {
      res.status(400).json({ message: 'chapterTitle is required' });
      return;
    }
    const db = await getDb();
    const doc = await db.collection(MAIN_COLLECTION).findOne({ _id: MAIN_DOC_ID });
    const items = Array.isArray(doc?.items) ? doc.items : [];
    const target = normalizeTitle(title);
    const match = items.find((item) => {
      const source = item?.content && typeof item.content === 'object' ? item.content : item;
      return [source?.chapter_name, source?.chapter_name_bn, item?.name].some((name) => normalizeTitle(name) === target);
    });
    if (!match) {
      res.status(404).json({ message: 'Chapter not found' });
      return;
    }
    const source = match?.content && typeof match.content === 'object' ? match.content : match;
    let lessons = [];
    if (Array.isArray(source?.lessons)) {
      lessons = source.lessons.map((lesson) => lesson?.lesson_name || lesson?.lesson_name_bn || lesson?.lesson_title || '').filter(Boolean);
    } else if (Array.isArray(source?.lesson_boundaries)) {
      lessons = source.lesson_boundaries.filter(Boolean);
    }
    res.json({ lessons });
  } catch (error) {
    res.status(500).json({ message: 'Failed to load lessons' });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
