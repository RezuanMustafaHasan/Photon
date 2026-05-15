import 'dotenv/config';

const DEFAULT_DEV_JWT_SECRET = 'dev_secret_change_me';
const MIN_SECRET_LENGTH = 32;

const isProduction = () => process.env.NODE_ENV === 'production';

const parseCsv = (value) => String(value || '')
  .split(',')
  .map((entry) => entry.trim())
  .filter(Boolean);

export const requireProductionSecret = (name, fallback) => {
  const value = String(process.env[name] || fallback || '').trim();

  if (isProduction()) {
    if (!value || value === fallback || value.length < MIN_SECRET_LENGTH) {
      throw new Error(`${name} must be set to a unique value with at least ${MIN_SECRET_LENGTH} characters in production.`);
    }
  }

  return value;
};

export const getJwtSecret = () => requireProductionSecret('JWT_SECRET', DEFAULT_DEV_JWT_SECRET);

export const getFastApiInternalApiKey = () => {
  const value = String(process.env.FASTAPI_INTERNAL_API_KEY || '').trim();

  if (isProduction() && value.length < MIN_SECRET_LENGTH) {
    throw new Error(`FASTAPI_INTERNAL_API_KEY must be set to a unique value with at least ${MIN_SECRET_LENGTH} characters in production.`);
  }

  return value;
};

export const createJsonHeaders = () => {
  const headers = { 'Content-Type': 'application/json' };
  const internalApiKey = getFastApiInternalApiKey();
  if (internalApiKey) {
    headers['X-Internal-API-Key'] = internalApiKey;
  }
  return headers;
};

export const createCorsOptions = () => {
  const configuredOrigins = parseCsv(process.env.CORS_ORIGINS || process.env.CLIENT_ORIGIN);
  const allowedOrigins = configuredOrigins.length
    ? configuredOrigins
    : [
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:5174',
        'http://127.0.0.1:5174',
      ];

  if (isProduction() && !configuredOrigins.length) {
    throw new Error('CORS_ORIGINS must be set in production.');
  }

  return {
    origin(origin, callback) {
      if (!origin) {
        callback(null, true);
        return;
      }

      if (allowedOrigins.includes(origin) || (!isProduction() && allowedOrigins.includes('*'))) {
        callback(null, true);
        return;
      }

      callback(new Error('Not allowed by CORS'));
    },
  };
};
