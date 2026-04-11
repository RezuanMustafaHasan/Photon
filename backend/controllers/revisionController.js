import {
  getTodayRevision,
  refreshRevisionTasks,
  reviewRevisionTask,
} from '../util/revision.js';

const VALID_OUTCOMES = new Set(['again', 'hard', 'good', 'easy']);

export const getToday = async (req, res) => {
  try {
    const payload = await getTodayRevision({ userId: req.userId });
    res.json(payload);
  } catch {
    res.status(500).json({ message: 'Failed to load today’s revision queue.' });
  }
};

export const refresh = async (req, res) => {
  try {
    const payload = await refreshRevisionTasks({ userId: req.userId });
    res.status(202).json(payload);
  } catch {
    res.status(500).json({ message: 'Failed to refresh revision queue.' });
  }
};

export const review = async (req, res) => {
  const outcome = String(req.body?.outcome || '').trim().toLowerCase();
  if (!VALID_OUTCOMES.has(outcome)) {
    res.status(400).json({ message: 'outcome must be one of again, hard, good, or easy.' });
    return;
  }

  try {
    const task = await reviewRevisionTask({
      userId: req.userId,
      taskId: req.params.taskId,
      outcome,
    });

    if (!task) {
      res.status(404).json({ message: 'Revision task not found.' });
      return;
    }

    res.json({ task });
  } catch {
    res.status(500).json({ message: 'Failed to update revision task.' });
  }
};
