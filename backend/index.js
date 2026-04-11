import dotenv from 'dotenv';
import connectDB from './util/db.js';
import createApp from './app.js';
import { connectRedis, isRateLimitEnabled } from './util/redisClient.js';

dotenv.config();

const PORT = process.env.PORT || 5000;
const rateLimitEnabled = isRateLimitEnabled();

const startServer = async () => {
  const redisPromise = rateLimitEnabled
    ? connectRedis({ required: true })
    : Promise.resolve(null);

  const [redisClient] = await Promise.all([
    redisPromise,
    connectDB(process.env.MONGODB_URI || 'mongodb://localhost:27017/hsc_physics_db'),
  ]);

  const app = createApp({
    rateLimit: {
      enabled: rateLimitEnabled,
      redisClient,
    },
  });

  app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
  });
};

startServer().catch((error) => {
  console.error('Server startup error:', error);
  process.exit(1);
});
