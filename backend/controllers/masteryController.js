import { getMasterySummary, recordLessonActivity } from '../util/mastery.js';
import { refreshRevisionTasks } from '../util/revision.js';

const normalizeString = (value) => (typeof value === 'string' ? value.trim() : '');
const logBestEffortError = (label, error) => {
  if (error?.name === 'MongoClientClosedError') {
    return;
  }
  console.error(label, error);
};

export const getSummary = async (req, res) => {
  try {
    const summary = await getMasterySummary({ userId: req.userId });
    res.json(summary);
  } catch {
    res.status(500).json({ message: 'Failed to load mastery summary.' });
  }
};

export const saveLessonActivity = async (req, res) => {
  const chapterName = normalizeString(req.body?.chapterName);
  const lessonName = normalizeString(req.body?.lessonName);
  const seconds = Number(req.body?.seconds);

  if (!chapterName || !lessonName) {
    res.status(400).json({ message: 'chapterName and lessonName are required.' });
    return;
  }

  if (!Number.isFinite(seconds) || seconds <= 0) {
    res.status(400).json({ message: 'seconds must be a positive number.' });
    return;
  }

  try {
    const activity = await recordLessonActivity({
      userId: req.userId,
      chapterName,
      lessonName,
      seconds,
    });

    if (activity) {
      refreshRevisionTasks({ userId: req.userId }).catch((error) => {
        logBestEffortError('Revision refresh after lesson activity error:', error);
      });
    }

    res.status(202).json({ ok: true });
  } catch {
    res.status(500).json({ message: 'Failed to save lesson activity.' });
  }
};
