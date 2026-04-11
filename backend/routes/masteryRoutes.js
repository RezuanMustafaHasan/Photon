import { Router } from 'express';
import authMiddleware from '../middleware/authMiddleware.js';
import { getSummary, saveLessonActivity } from '../controllers/masteryController.js';

const createMasteryRouter = () => {
  const router = Router();

  router.get('/summary', authMiddleware, getSummary);
  router.post('/lesson-activity', authMiddleware, saveLessonActivity);

  return router;
};

export default createMasteryRouter;
