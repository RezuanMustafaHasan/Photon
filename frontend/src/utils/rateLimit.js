const RATE_LIMIT_STORAGE_KEY = 'photon_rate_limit_notice';
const PAGE_LOAD_RATE_LIMIT_PREFIX = 'photon_page_load_rate_limit:';

export const createRateLimitNotice = (
  data,
  headers,
  fallbackMessage = 'Too many requests. Please wait and try again.',
) => {
  const payloadRetryAfter = Number(data?.retryAfterSeconds);
  const headerRetryAfter = Number(headers?.get?.('Retry-After'));
  const retryAfterSeconds = Math.max(
    1,
    Number.isFinite(payloadRetryAfter) && payloadRetryAfter > 0
      ? Math.ceil(payloadRetryAfter)
      : (Number.isFinite(headerRetryAfter) && headerRetryAfter > 0 ? Math.ceil(headerRetryAfter) : 60),
  );

  const parsedResetAt = Date.parse(String(data?.resetAt || ''));
  const resetAt = new Date(
    Number.isFinite(parsedResetAt)
      ? parsedResetAt
      : Date.now() + retryAfterSeconds * 1000,
  ).toISOString();

  return {
    code: String(data?.code || 'rate_limit_exceeded'),
    policy: String(data?.policy || ''),
    message: String(data?.message || fallbackMessage),
    retryAfterSeconds,
    resetAt,
  };
};

export const getRateLimitRemainingSeconds = (notice, now = Date.now()) => {
  if (!notice?.resetAt) {
    return 0;
  }

  const resetAt = Date.parse(notice.resetAt);
  if (!Number.isFinite(resetAt)) {
    return Math.max(0, Number(notice.retryAfterSeconds) || 0);
  }

  return Math.max(0, Math.ceil((resetAt - now) / 1000));
};

export const formatRateLimitWait = (seconds) => {
  const safeSeconds = Math.max(0, Number(seconds) || 0);
  if (safeSeconds >= 60) {
    const minutes = Math.floor(safeSeconds / 60);
    const remainingSeconds = safeSeconds % 60;
    return remainingSeconds ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }
  return `${safeSeconds}s`;
};

const canUseStorage = () => typeof window !== 'undefined' && typeof window.sessionStorage !== 'undefined';

export const readStoredRateLimitNotice = () => {
  if (!canUseStorage()) {
    return null;
  }

  const raw = window.sessionStorage.getItem(RATE_LIMIT_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw);
    if (getRateLimitRemainingSeconds(parsed) <= 0) {
      window.sessionStorage.removeItem(RATE_LIMIT_STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    window.sessionStorage.removeItem(RATE_LIMIT_STORAGE_KEY);
    return null;
  }
};

export const persistRateLimitNotice = (notice) => {
  if (!canUseStorage()) {
    return;
  }

  if (!notice || getRateLimitRemainingSeconds(notice) <= 0) {
    window.sessionStorage.removeItem(RATE_LIMIT_STORAGE_KEY);
    return;
  }

  window.sessionStorage.setItem(RATE_LIMIT_STORAGE_KEY, JSON.stringify(notice));
};

export const clearStoredRateLimitNotice = () => {
  if (!canUseStorage()) {
    return;
  }

  window.sessionStorage.removeItem(RATE_LIMIT_STORAGE_KEY);
};

const getPageLoadStorageKey = (pathname) => `${PAGE_LOAD_RATE_LIMIT_PREFIX}${pathname || '/'}`;

export const registerPageLoadRateLimit = ({
  pathname,
  limit = 20,
  windowMs = 60 * 1000,
  message = 'You are refreshing this page too quickly. Please wait a moment before loading it again.',
} = {}) => {
  if (!canUseStorage()) {
    return null;
  }

  const storageKey = getPageLoadStorageKey(pathname);
  const now = Date.now();

  let timestamps = [];
  try {
    timestamps = JSON.parse(window.sessionStorage.getItem(storageKey) || '[]');
  } catch {
    timestamps = [];
  }

  const validTimestamps = Array.isArray(timestamps)
    ? timestamps.filter((timestamp) => Number.isFinite(timestamp) && now - timestamp < windowMs)
    : [];

  validTimestamps.push(now);
  window.sessionStorage.setItem(storageKey, JSON.stringify(validTimestamps));

  if (validTimestamps.length <= limit) {
    return null;
  }

  const resetAtMs = validTimestamps[0] + windowMs;
  const retryAfterSeconds = Math.max(1, Math.ceil((resetAtMs - now) / 1000));

  return {
    code: 'rate_limit_exceeded',
    policy: 'page-reload',
    message,
    retryAfterSeconds,
    resetAt: new Date(resetAtMs).toISOString(),
  };
};
