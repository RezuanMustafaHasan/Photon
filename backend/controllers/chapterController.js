import {
  findChapterInSyllabus,
  findLessonInChapter,
  getSyllabusOutline,
} from '../util/syllabus.js';

export const getChapters = async (_req, res) => {
  try {
    const syllabus = await getSyllabusOutline();
    const chapters = syllabus
      .map((chapter) => ({
        chapter_name: chapter.chapterNameEn || chapter.chapterName,
        chapter_name_bn: chapter.chapterName,
      }))
      .filter((chapter) => chapter.chapter_name_bn);

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

    const syllabus = await getSyllabusOutline();
    const chapter = findChapterInSyllabus(syllabus, title);
    if (!chapter) {
      res.status(404).json({ message: 'Chapter not found' });
      return;
    }

    res.json({ lessons: chapter.lessons.map((lesson) => lesson.lessonName) });
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

    const syllabus = await getSyllabusOutline();
    const chapter = findChapterInSyllabus(syllabus, chapterTitle);
    if (!chapter) {
      res.status(404).json({ message: 'Chapter not found' });
      return;
    }

    const lesson = findLessonInChapter(chapter, lessonTitle);
    if (!lesson) {
      res.status(404).json({ message: 'Lesson not found' });
      return;
    }

    res.json({
      lesson: {
        lesson_name: lesson.lessonName,
      },
    });
  } catch {
    res.status(500).json({ message: 'Failed to load lesson' });
  }
};
