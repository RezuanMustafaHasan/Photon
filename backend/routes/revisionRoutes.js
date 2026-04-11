import { Router } from 'express';
import authMiddleware from '../middleware/authMiddleware.js';
import { getToday, refresh, review } from '../controllers/revisionController.js';

const createRevisionRouter = () => {
  const router = Router();

  router.get('/today', authMiddleware, getToday);
  router.post('/refresh', authMiddleware, refresh);
  router.post('/:taskId/review', authMiddleware, review);

  return router;
};

export default createRevisionRouter;
