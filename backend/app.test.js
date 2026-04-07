import assert from 'node:assert/strict';
import test from 'node:test';
import jwt from 'jsonwebtoken';
import request from 'supertest';
import { createApp } from './app.js';

const JWT_SECRET = 'dev_secret_change_me';
const originalFetch = global.fetch;

const createToken = (userId) => jwt.sign({ sub: userId }, JWT_SECRET, { expiresIn: '1h' });

const createUpstreamResponse = (body = { response: 'ok' }, status = 200) => (
  new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json',
    },
  })
);

const sendChat = (app, token, userId = 'spoofed-user') => request(app)
  .post('/api/chat')
  .set('Authorization', `Bearer ${token}`)
  .send({
    message: 'Explain Newtons first law.',
    userId,
    chapterName: 'Force',
    lessonName: 'Newtons laws',
  });

test('chat limiter returns a consistent 429 payload and headers', async (t) => {
  global.fetch = async () => createUpstreamResponse();
  t.after(() => {
    global.fetch = originalFetch;
  });

  const app = createApp({
    rateLimit: {
      enabled: true,
      redisClient: null,
    },
  });
  const token = createToken('chat-user');

  for (let index = 0; index < 20; index += 1) {
    await sendChat(app, token, `spoof-${index}`).expect(200);
  }

  const blocked = await sendChat(app, token, 'fresh-spoof').expect(429);

  assert.equal(blocked.body.code, 'rate_limit_exceeded');
  assert.equal(blocked.body.policy, 'chat-send');
  assert.ok(Number.isInteger(blocked.body.retryAfterSeconds));
  assert.ok(blocked.body.retryAfterSeconds > 0);
  assert.ok(blocked.body.resetAt);
  assert.match(blocked.body.message, /messages too quickly/i);
  assert.ok(blocked.headers['retry-after']);
  assert.ok(blocked.headers.ratelimit);
});

test('chat limiter keys off the authenticated user instead of the request body userId', async (t) => {
  global.fetch = async () => createUpstreamResponse();
  t.after(() => {
    global.fetch = originalFetch;
  });

  const app = createApp({
    rateLimit: {
      enabled: true,
      redisClient: null,
    },
  });
  const token = createToken('real-user');

  for (let index = 0; index < 20; index += 1) {
    await sendChat(app, token, `spoof-${index}`).expect(200);
  }

  await sendChat(app, token, 'totally-different-user').expect(429);
});

test('chat controller forwards the JWT user id to the upstream service', async (t) => {
  let forwardedBody = null;
  global.fetch = async (_url, init) => {
    forwardedBody = JSON.parse(init.body);
    return createUpstreamResponse({ response: 'Forwarded correctly' });
  };
  t.after(() => {
    global.fetch = originalFetch;
  });

  const app = createApp({
    rateLimit: {
      enabled: false,
      redisClient: null,
    },
  });
  const token = createToken('trusted-user');

  await sendChat(app, token, 'spoofed-user').expect(200);

  assert.equal(forwardedBody.user_id, 'trusted-user');
  assert.equal(forwardedBody.chapter_name, 'Force');
  assert.equal(forwardedBody.lesson_name, 'Newtons laws');
});
