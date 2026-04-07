import { Router } from 'express';
import { getChapters, getLesson, getLessons } from '../controllers/chapterController.js';

const passthrough = (_req, _res, next) => {
  next();
};

export const createChapterRouter = ({ chapterReadLimiter = passthrough } = {}) => {
  const router = Router();

  router.get('/', chapterReadLimiter, getChapters);
  router.get('/:chapterTitle/lessons', chapterReadLimiter, getLessons);
  router.get('/:chapterTitle/lessons/:lessonTitle', chapterReadLimiter, getLesson);

  return router;
};

export default createChapterRouter;
