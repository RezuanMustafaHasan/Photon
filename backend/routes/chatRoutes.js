import { Router } from 'express';
import { chat, history, clearHistory } from '../controllers/chatController.js';
import authMiddleware from '../middleware/authMiddleware.js';

const passthrough = (_req, _res, next) => {
  next();
};

export const createChatRouter = ({
  chatSendLimiter = passthrough,
  chatHistoryLimiter = passthrough,
} = {}) => {
  const router = Router();

  router.post('/', authMiddleware, chatSendLimiter, chat);
  router.get('/history', authMiddleware, chatHistoryLimiter, history);
  router.delete('/history', authMiddleware, chatHistoryLimiter, clearHistory);

  return router;
};

export default createChatRouter;
