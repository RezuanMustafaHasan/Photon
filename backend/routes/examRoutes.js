import { Router } from 'express';
import authMiddleware from '../middleware/authMiddleware.js';
import { completeExam, generateExam, getExamAttempt, getExamHistory } from '../controllers/examController.js';

const router = Router();

router.post('/generate', authMiddleware, generateExam);
router.post('/complete', authMiddleware, completeExam);
router.get('/history', authMiddleware, getExamHistory);
router.get('/:attemptId', authMiddleware, getExamAttempt);

export default router;
