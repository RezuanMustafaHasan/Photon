import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import connectDB from './util/db.js';
import authRoutes from './routes/authRoutes.js';
import chatRoutes from './routes/chatRoutes.js';
import chapterRoutes from './routes/chapterRoutes.js';
import examRoutes from './routes/examRoutes.js';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors({ origin: true }));
app.use(express.json());

app.get('/', (req, res) => {
  res.send('API is running...');
});

app.use('/api/auth', authRoutes);
app.use('/api/chat', chatRoutes);
app.use('/api/chapters', chapterRoutes);
app.use('/api/exams', examRoutes);

connectDB(process.env.MONGODB_URI || 'mongodb://localhost:27017/hsc_physics_db')
  .then(() => {
    app.listen(PORT, () => {
      console.log(`Server running on port ${PORT}`);
    });
  })
  .catch((err) => {
    console.error('MongoDB connection error:', err);
    process.exit(1);
  });
