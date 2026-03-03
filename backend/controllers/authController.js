import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import User from '../models/User.js';

const JWT_SECRET = process.env.JWT_SECRET || 'dev_secret_change_me';

const createAuthPayload = (user) => {
  const token = jwt.sign({ sub: user._id.toString() }, JWT_SECRET, { expiresIn: '7d' });
  return {
    token,
    user: {
      id: user._id.toString(),
      name: user.name,
      email: user.email,
    },
  };
};

export const signup = async (req, res) => {
  try {
    const name = String(req.body?.name || '').trim();
    const email = String(req.body?.email || '').trim().toLowerCase();
    const password = String(req.body?.password || '');

    if (!name || name.length < 2) {
      res.status(400).json({ message: 'Full name is required.' });
      return;
    }
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      res.status(400).json({ message: 'Enter a valid email address.' });
      return;
    }
    if (!password || password.length < 8) {
      res.status(400).json({ message: 'Password must be at least 8 characters.' });
      return;
    }

    const existing = await User.findOne({ email }).lean();
    if (existing) {
      res.status(409).json({ message: 'An account with that email already exists.' });
      return;
    }

    const passwordHash = await bcrypt.hash(password, 10);
    const user = await User.create({ name, email, passwordHash });
    res.status(201).json(createAuthPayload(user));
  } catch {
    res.status(500).json({ message: 'Server error.' });
  }
};

export const login = async (req, res) => {
  try {
    const email = String(req.body?.email || '').trim().toLowerCase();
    const password = String(req.body?.password || '');

    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      res.status(400).json({ message: 'Enter a valid email address.' });
      return;
    }
    if (!password) {
      res.status(400).json({ message: 'Password is required.' });
      return;
    }

    const user = await User.findOne({ email });
    if (!user) {
      res.status(401).json({ message: 'Invalid email or password.' });
      return;
    }

    const ok = await bcrypt.compare(password, user.passwordHash);
    if (!ok) {
      res.status(401).json({ message: 'Invalid email or password.' });
      return;
    }

    res.json(createAuthPayload(user));
  } catch {
    res.status(500).json({ message: 'Server error.' });
  }
};

export const me = async (req, res) => {
  try {
    const user = await User.findById(req.userId).lean();
    if (!user) {
      res.status(404).json({ message: 'User not found.' });
      return;
    }
    res.json({ id: user._id.toString(), name: user.name, email: user.email });
  } catch {
    res.status(500).json({ message: 'Server error.' });
  }
};
