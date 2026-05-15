import jwt from 'jsonwebtoken';
import { getJwtSecret } from '../util/security.js';

const JWT_SECRET = getJwtSecret();

const authMiddleware = (req, res, next) => {
  const header = req.headers.authorization || '';
  const [type, token] = header.split(' ');
  if (type !== 'Bearer' || !token) {
    res.status(401).json({ message: 'Unauthorized.' });
    return;
  }
  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    req.userId = decoded.sub;
    next();
  } catch {
    res.status(401).json({ message: 'Unauthorized.' });
  }
};

export default authMiddleware;
