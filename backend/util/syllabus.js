import mongoose from 'mongoose';

const MAIN_COLLECTION = 'main_book';
const MAIN_DOC_ID = 'main_book';

export const normalizeTitle = (value) => String(value || '').trim().toLowerCase();

const getDb = async () => {
  if (mongoose.connection.readyState !== 1) {
    await mongoose.connection.asPromise();
  }

  return mongoose.connection.db;
};

const getChapterSource = (item) => {
  if (item?.content && typeof item.content === 'object') {
    return item.content;
  }

  return item;
};

const normalizeAliases = (values) => Array.from(
  new Set(
    values
      .map((value) => String(value || '').trim())
      .filter(Boolean),
  ),
);

const mapLessonEntry = (lesson) => {
  const lessonName = String(
    lesson?.lesson_name
    || lesson?.lesson_name_bn
    || lesson?.lesson_title
    || '',
  ).trim();

  return {
    lessonName,
    aliases: normalizeAliases([
      lesson?.lesson_name,
      lesson?.lesson_name_bn,
      lesson?.lesson_title,
    ]),
  };
};

export const getSyllabusOutline = async () => {
  const db = await getDb();
  const doc = await db.collection(MAIN_COLLECTION).findOne({ _id: MAIN_DOC_ID });
  const items = Array.isArray(doc?.items) ? doc.items : [];

  return items
    .map((item) => {
      const source = getChapterSource(item);
      const chapterName = String(
        source?.chapter_name_bn
        || source?.chapter_name
        || item?.name
        || '',
      ).trim();

      const chapterNameEn = String(source?.chapter_name || item?.name || '').trim();
      const lessons = Array.isArray(source?.lessons)
        ? source.lessons.map(mapLessonEntry).filter((lessonEntry) => lessonEntry.lessonName)
        : Array.isArray(source?.lesson_boundaries)
        ? source.lesson_boundaries
          .map((lessonName) => mapLessonEntry({ lesson_name: lessonName }))
          .filter((lessonEntry) => lessonEntry.lessonName)
        : [];

      return {
        chapterName,
        chapterNameEn,
        aliases: normalizeAliases([
          source?.chapter_name,
          source?.chapter_name_bn,
          item?.name,
        ]),
        lessons,
      };
    })
    .filter((chapter) => chapter.chapterName);
};

export const findChapterInSyllabus = (syllabus, chapterTitle) => {
  const target = normalizeTitle(chapterTitle);

  return (Array.isArray(syllabus) ? syllabus : []).find((chapter) => (
    Array.isArray(chapter.aliases)
      && chapter.aliases.some((alias) => normalizeTitle(alias) === target)
  )) || null;
};

export const findLessonInChapter = (chapter, lessonTitle) => {
  const target = normalizeTitle(lessonTitle);

  return (Array.isArray(chapter?.lessons) ? chapter.lessons : []).find((lesson) => (
    Array.isArray(lesson.aliases)
      && lesson.aliases.some((alias) => normalizeTitle(alias) === target)
  )) || null;
};
