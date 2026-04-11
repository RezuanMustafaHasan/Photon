import { Router } from 'express';
import { chat, history, clearHistory } from '../controllers/chatController.js';

const router = Router();

router.post('/', chat);
router.get('/history', history);
router.delete('/history', clearHistory);

export default router;
