import { createClient } from 'redis';

let sharedRedisClient = null;
let redisConnectPromise = null;

const getRedisUrl = () => String(process.env.UPSTASH_REDIS_URL || '').trim();

export const isRateLimitEnabled = () => String(process.env.RATE_LIMIT_ENABLED || '').trim().toLowerCase() === 'true';

export const connectRedis = async ({ required = false } = {}) => {
  const redisUrl = getRedisUrl();

  if (!redisUrl) {
    if (required) {
      throw new Error('UPSTASH_REDIS_URL is required when RATE_LIMIT_ENABLED=true.');
    }
    return null;
  }

  if (sharedRedisClient?.isOpen) {
    return sharedRedisClient;
  }

  if (!redisConnectPromise) {
    const parsedUrl = new URL(redisUrl);
    if (parsedUrl.hostname.endsWith('.upstash.io') && parsedUrl.protocol === 'redis:') {
      throw new Error('Upstash Redis requires a TLS connection. Change UPSTASH_REDIS_URL from redis:// to rediss://');
    }

    const client = createClient({ url: redisUrl });

    client.on('error', (error) => {
      console.error('Redis client error:', error);
    });

    redisConnectPromise = client.connect()
      .then(() => {
        sharedRedisClient = client;
        return client;
      })
      .catch((error) => {
        redisConnectPromise = null;
        throw error;
      });
  }

  return redisConnectPromise;
};

export const getRedisClient = () => sharedRedisClient;
