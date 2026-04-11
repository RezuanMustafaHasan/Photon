import { Router } from 'express';
import { login, me, signup } from '../controllers/authController.js';
import authMiddleware from '../middleware/authMiddleware.js';

const passthrough = (_req, _res, next) => {
  next();
};

export const createAuthRouter = ({ authWriteLimiter = passthrough } = {}) => {
  const router = Router();

  router.post('/signup', authWriteLimiter, signup);
  router.post('/login', authWriteLimiter, login);
  router.get('/me', authMiddleware, me);

  return router;
};

export default createAuthRouter;
