import mongoose from 'mongoose';
import { recordChatConfusion } from '../util/mastery.js';
import { refreshRevisionTasks } from '../util/revision.js';

const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL || 'http://localhost:8000';
const FASTAPI_CHAT_URL = `${FASTAPI_BASE_URL}/chat`;
const FASTAPI_CHAT_HISTORY_URL = `${FASTAPI_BASE_URL}/chat/history`;

const logBestEffortError = (label, error) => {
  if (error?.name === 'MongoClientClosedError') {
    return;
  }
  console.error(label, error);
};

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

const normalizeString = (value) => (typeof value === 'string' ? value.trim() : '');

const normalizeCitation = (value) => {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const chapterName = normalizeString(value.chapterName ?? value.chapter_name);
  const lessonName = normalizeString(value.lessonName ?? value.lesson_name);
  const sectionLabel = normalizeString(value.sectionLabel ?? value.section_label);
  const snippet = normalizeString(value.snippet);

  if (!chapterName && !lessonName && !sectionLabel && !snippet) {
    return null;
  }

  return {
    chapterName,
    lessonName,
    sectionLabel,
    snippet,
  };
};

const normalizeImages = (value) => (Array.isArray(value)
  ? value
      .map((item) => {
        const imageURL = normalizeString(item?.imageURL ?? item?.imageUrl ?? item?.url);
        if (!imageURL) {
          return null;
        }

        return {
          imageURL,
          description: normalizeString(item?.description ?? item?.caption),
          topic: Array.isArray(item?.topic)
            ? item.topic
                .map((entry) => normalizeString(entry))
                .filter(Boolean)
            : [],
        };
      })
      .filter(Boolean)
  : []);

export const mapUpstreamChatResponse = (value) => {
  const citations = Array.isArray(value?.citations)
    ? value.citations.map(normalizeCitation).filter(Boolean)
    : [];
  const images = normalizeImages(value?.images);

  return {
    response: normalizeString(value?.response),
    textbookAnswer: normalizeString(value?.textbook_answer ?? value?.textbookAnswer),
    extraExplanation: normalizeString(value?.extra_explanation ?? value?.extraExplanation),
    citations,
    images,
  };
};

export const mapStoredHistoryEntry = (value) => {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const role = value.role === 'assistant' ? 'assistant' : 'user';
  const content = normalizeString(value.content);

  if (role !== 'assistant') {
    return {
      role,
      content,
    };
  }

  const mapped = {
    role,
    content,
    textbookAnswer: normalizeString(value.textbookAnswer ?? value.textbook_answer),
    extraExplanation: normalizeString(value.extraExplanation ?? value.extra_explanation),
    citations: Array.isArray(value.citations)
      ? value.citations.map(normalizeCitation).filter(Boolean)
      : [],
  };

  const images = normalizeImages(value.images);
  if (images.length > 0) {
    mapped.images = images;
  }

  return mapped;
};

export const chat = async (req, res) => {
  const message = typeof req.body?.message === 'string' ? req.body.message.trim() : '';
  const userId = typeof req.userId === 'string' ? req.userId.trim() : '';
  const chapterName = typeof req.body?.chapterName === 'string' ? req.body.chapterName.trim() : '';
  const lessonName = typeof req.body?.lessonName === 'string' ? req.body.lessonName.trim() : '';
  const historyMode = req.body?.historyMode === 'assistant_only' ? 'assistant_only' : 'default';
  const chatModel = typeof req.body?.chatModel === 'string' ? req.body.chatModel.trim() : '';
  const requestStartedAt = Date.now();

  console.log(`[chat] backend start user=${userId} chapter=${chapterName} lesson=${lessonName}`);

  if (!message || !userId || !chapterName || !lessonName) {
    res.status(400).json({ message: 'message, chapterName, and lessonName are required' });
    return;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  try {
    const upstreamStartedAt = Date.now();
    console.log(`[chat] backend -> fastapi start user=${userId} lesson=${lessonName}`);

    const upstreamPayload = {
      message,
      user_id: userId,
      chapter_name: chapterName,
      lesson_name: lessonName,
      history_mode: historyMode,
    };
    if (chatModel) {
      upstreamPayload.chat_model = chatModel;
    }

    const upstream = await fetch(FASTAPI_CHAT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(upstreamPayload),
      signal: controller.signal,
    });

    const data = await upstream.json().catch(() => null);
    console.log(
      `[chat] backend -> fastapi done user=${userId} lesson=${lessonName} status=${upstream.status} upstream_ms=${Date.now() - upstreamStartedAt} total_ms=${Date.now() - requestStartedAt}`,
    );
    if (!upstream.ok) {
      res.status(502).json({ message: data?.detail || data?.message || 'Upstream error' });
      return;
    }

    recordChatConfusion({
      userId,
      chapterName,
      lessonName,
      message,
    }).then((changed) => {
      if (changed) {
        return refreshRevisionTasks({ userId });
      }
      return null;
    }).catch((error) => {
      logBestEffortError('Mastery chat signal error:', error);
    });

    res.json(mapUpstreamChatResponse(data));
  } catch {
    console.log(
      `[chat] backend error user=${userId} lesson=${lessonName} total_ms=${Date.now() - requestStartedAt}`,
    );
    res.status(502).json({ message: 'FastAPI is unreachable' });
  } finally {
    clearTimeout(timeoutId);
  }
};

export const history = async (req, res) => {
  const userId = typeof req.userId === 'string' ? req.userId.trim() : '';
  const chapterName = typeof req.query?.chapterName === 'string' ? req.query.chapterName.trim() : '';
  const lessonName = typeof req.query?.lessonName === 'string' ? req.query.lessonName.trim() : '';

  if (!userId || !chapterName || !lessonName) {
    res.status(400).json({ message: 'chapterName and lessonName are required' });
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
    const historyEntries = Array.isArray(doc?.history) ? doc.history.map(mapStoredHistoryEntry).filter(Boolean) : [];
    res.json({ history: historyEntries });
  } catch {
    res.status(500).json({ message: 'Failed to load history' });
  }
};

export const clearHistory = async (req, res) => {
  const userId = typeof req.userId === 'string' ? req.userId.trim() : '';
  const chapterName = typeof req.body?.chapterName === 'string' ? req.body.chapterName.trim() : '';
  const lessonName = typeof req.body?.lessonName === 'string' ? req.body.lessonName.trim() : '';

  if (!userId || !chapterName || !lessonName) {
    res.status(400).json({ message: 'chapterName and lessonName are required' });
    return;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  try {
    const upstream = await fetch(FASTAPI_CHAT_HISTORY_URL, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        chapter_name: chapterName,
        lesson_name: lessonName,
      }),
      signal: controller.signal,
    });

    const data = await upstream.json().catch(() => null);
    if (!upstream.ok) {
      res.status(502).json({ message: data?.detail || data?.message || 'Upstream error' });
      return;
    }

    res.json({ deleted: Boolean(data?.deleted) });
  } catch {
    res.status(502).json({ message: 'FastAPI is unreachable' });
  } finally {
    clearTimeout(timeoutId);
  }
};
