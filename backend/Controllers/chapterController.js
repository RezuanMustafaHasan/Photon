import mongoose from 'mongoose';

const MAIN_COLLECTION = 'main_book';
const MAIN_DOC_ID = 'main_book';

const getDb = async () => {
  if (mongoose.connection.readyState !== 1) {
    await mongoose.connection.asPromise();
  }
  return mongoose.connection.db;
};

const normalizeTitle = (value) => String(value || '').trim().toLowerCase();

const getMainItems = async () => {
  const db = await getDb();
  const doc = await db.collection(MAIN_COLLECTION).findOne({ _id: MAIN_DOC_ID });
  return Array.isArray(doc?.items) ? doc.items : [];
};

const getChapterSource = (item) => {
  if (item?.content && typeof item.content === 'object') {
    return item.content;
  }
  return item;
};

const findChapterItem = (items, title) => {
  const target = normalizeTitle(title);
  return items.find((item) => {
    const source = getChapterSource(item);
    return [source?.chapter_name, source?.chapter_name_bn, item?.name].some((name) => normalizeTitle(name) === target);
  });
};

export const getChapters = async (req, res) => {
  try {
    const items = await getMainItems();
    const chapters = items.map((item) => {
      const source = getChapterSource(item);
      const chapterName = source?.chapter_name || item?.name || '';
      const chapterNameBn = source?.chapter_name_bn || source?.chapter_name || chapterName;
      return {
        chapter_name: chapterName,
        chapter_name_bn: chapterNameBn,
      };
    }).filter((chapter) => chapter.chapter_name_bn);
    res.json({ chapters });
  } catch {
    res.status(500).json({ message: 'Failed to load chapters' });
  }
};

export const getLessons = async (req, res) => {
  try {
    const title = req.params.chapterTitle;
    if (!title) {
      res.status(400).json({ message: 'chapterTitle is required' });
      return;
    }
    const items = await getMainItems();
    const match = findChapterItem(items, title);
    if (!match) {
      res.status(404).json({ message: 'Chapter not found' });
      return;
    }
    const source = getChapterSource(match);
    let lessons = [];
    if (Array.isArray(source?.lessons)) {
      lessons = source.lessons.map((lesson) => lesson?.lesson_name || lesson?.lesson_name_bn || lesson?.lesson_title || '').filter(Boolean);
    } else if (Array.isArray(source?.lesson_boundaries)) {
      lessons = source.lesson_boundaries.filter(Boolean);
    }
    res.json({ lessons });
  } catch {
    res.status(500).json({ message: 'Failed to load lessons' });
  }
};

export const getLesson = async (req, res) => {
  try {
    const chapterTitle = req.params.chapterTitle;
    const lessonTitle = req.params.lessonTitle;
    if (!chapterTitle || !lessonTitle) {
      res.status(400).json({ message: 'chapterTitle and lessonTitle are required' });
      return;
    }
    const items = await getMainItems();
    const match = findChapterItem(items, chapterTitle);
    if (!match) {
      res.status(404).json({ message: 'Chapter not found' });
      return;
    }
    const source = getChapterSource(match);
    if (!Array.isArray(source?.lessons)) {
      res.status(404).json({ message: 'Lessons not found' });
      return;
    }
    const target = normalizeTitle(lessonTitle);
    const lesson = source.lessons.find((entry) => {
      return [entry?.lesson_name, entry?.lesson_name_bn, entry?.lesson_title].some((name) => normalizeTitle(name) === target);
    });
    if (!lesson) {
      res.status(404).json({ message: 'Lesson not found' });
      return;
    }
    res.json({ lesson });
  } catch {
    res.status(500).json({ message: 'Failed to load lesson' });
  }
};