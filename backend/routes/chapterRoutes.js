import { Router } from 'express';
import { getChapters, getLesson, getLessons } from '../controllers/chapterController.js';

const router = Router();

router.get('/', getChapters);
router.get('/:chapterTitle/lessons', getLessons);
router.get('/:chapterTitle/lessons/:lessonTitle', getLesson);

export default router;
