import mongoose from 'mongoose';

const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL || 'http://localhost:8000';
const FASTAPI_CHAT_URL = `${FASTAPI_BASE_URL}/chat`;

const getDb = async () => {
  if (mongoose.connection.readyState !== 1) {
    await mongoose.connection.asPromise();
  }
  return mongoose.connection.db;
};

const parseUserId = (value) => {
  if (mongoose.Types.ObjectId.isValid(value)) {
    return new mongoose.Types.ObjectId(value);
  }
  return value;
};

export const chat = async (req, res) => {
  const message = typeof req.body?.message === 'string' ? req.body.message.trim() : '';
  const userId = typeof req.body?.userId === 'string' ? req.body.userId.trim() : '';
  const chapterName = typeof req.body?.chapterName === 'string' ? req.body.chapterName.trim() : '';
  const lessonName = typeof req.body?.lessonName === 'string' ? req.body.lessonName.trim() : '';

  if (!message || !userId || !chapterName || !lessonName) {
    res.status(400).json({ message: 'message, userId, chapterName, lessonName are required' });
    return;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  try {
    const upstream = await fetch(FASTAPI_CHAT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, user_id: userId, chapter_name: chapterName, lesson_name: lessonName }),
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
};

export const history = async (req, res) => {
  const userId = typeof req.query?.userId === 'string' ? req.query.userId.trim() : '';
  const chapterName = typeof req.query?.chapterName === 'string' ? req.query.chapterName.trim() : '';
  const lessonName = typeof req.query?.lessonName === 'string' ? req.query.lessonName.trim() : '';

  if (!userId || !chapterName || !lessonName) {
    res.status(400).json({ message: 'userId, chapterName, lessonName are required' });
    return;
  }

  try {
    const db = await getDb();
    const key = parseUserId(userId);
    const doc = await db.collection('chats').findOne({
      user_id: key,
      chapter_name: chapterName,
      lesson_name: lessonName,
    });
    res.json({ history: Array.isArray(doc?.history) ? doc.history : [] });
  } catch {
    res.status(500).json({ message: 'Failed to load history' });
  }
};
