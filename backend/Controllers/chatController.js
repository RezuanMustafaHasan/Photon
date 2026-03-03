const FASTAPI_CHAT_URL = process.env.FASTAPI_CHAT_URL || 'http://localhost:8000/chat';

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
