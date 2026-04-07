import assert from 'node:assert/strict';
import test from 'node:test';
import jwt from 'jsonwebtoken';
import request from 'supertest';
import { createApp } from './app.js';
import { mapStoredHistoryEntry } from './controllers/chatController.js';

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

const sendChat = (app, token, userId = 'spoofed-user', extraBody = {}) => request(app)
  .post('/api/chat')
  .set('Authorization', `Bearer ${token}`)
  .send({
    message: 'Explain Newtons first law.',
    userId,
    chapterName: 'Force',
    lessonName: 'Newtons laws',
    ...extraBody,
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
    return createUpstreamResponse({
      response: '**From your lesson**\n\nForwarded correctly',
      textbook_answer: 'Forwarded correctly',
      extra_explanation: 'Extra explanation',
      citations: [
        {
          chapter_name: 'Force',
          lesson_name: 'Newtons laws',
          section_label: 'Page 1 / Newtons first law',
          snippet: 'A body remains at rest...',
        },
      ],
    });
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
  assert.equal(forwardedBody.history_mode, 'default');
});

test('chat route returns the structured grounded payload', async (t) => {
  global.fetch = async () => createUpstreamResponse({
    response: '**From your lesson**\n\nNewtons first law.',
    textbook_answer: 'Newtons first law says a body remains at rest or in uniform motion unless acted upon by an external force.',
    extra_explanation: 'Think of a moving bus continuing forward unless brakes or friction change its motion.',
    citations: [
      {
        chapter_name: 'Force',
        lesson_name: 'Newtons laws',
        section_label: 'Page 1 / Newtons first law',
        snippet: 'A body remains at rest or moves uniformly...',
      },
    ],
  });
  t.after(() => {
    global.fetch = originalFetch;
  });

  const app = createApp({
    rateLimit: {
      enabled: false,
      redisClient: null,
    },
  });
  const token = createToken('structured-user');

  const response = await sendChat(app, token).expect(200);

  assert.equal(response.body.textbookAnswer, 'Newtons first law says a body remains at rest or in uniform motion unless acted upon by an external force.');
  assert.equal(response.body.extraExplanation, 'Think of a moving bus continuing forward unless brakes or friction change its motion.');
  assert.equal(response.body.citations.length, 1);
  assert.deepEqual(response.body.citations[0], {
    chapterName: 'Force',
    lessonName: 'Newtons laws',
    sectionLabel: 'Page 1 / Newtons first law',
    snippet: 'A body remains at rest or moves uniformly...',
  });
});

test('history mapping helper supports both legacy and structured assistant entries', () => {
  assert.deepEqual(
    mapStoredHistoryEntry({
      role: 'assistant',
      content: 'Legacy plain-text answer.',
    }),
    {
      role: 'assistant',
      content: 'Legacy plain-text answer.',
      textbookAnswer: '',
      extraExplanation: '',
      citations: [],
    },
  );

  assert.deepEqual(
    mapStoredHistoryEntry({
      role: 'assistant',
      content: '**From your lesson**\n\nStructured answer.',
      textbook_answer: 'Structured answer.',
      extra_explanation: 'Extra help.',
      citations: [
        {
          chapter_name: 'Static Electricity',
          lesson_name: 'Coulombs law',
          section_label: 'Page 3 / Coulombs law',
          snippet: 'Force is inversely proportional to the square of distance.',
        },
      ],
    }),
    {
      role: 'assistant',
      content: '**From your lesson**\n\nStructured answer.',
      textbookAnswer: 'Structured answer.',
      extraExplanation: 'Extra help.',
      citations: [
        {
          chapterName: 'Static Electricity',
          lessonName: 'Coulombs law',
          sectionLabel: 'Page 3 / Coulombs law',
          snippet: 'Force is inversely proportional to the square of distance.',
        },
      ],
    },
  );
});

test('chat controller forwards assistant-only history mode for source introductions', async (t) => {
  let forwardedBody = null;
  global.fetch = async (_url, init) => {
    forwardedBody = JSON.parse(init.body);
    return createUpstreamResponse({
      response: '**From your lesson**\n\nSource intro',
      textbook_answer: 'Source intro',
      extra_explanation: '',
      citations: [],
    });
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
  const token = createToken('source-user');

  await sendChat(app, token, 'spoofed-user', {
    historyMode: 'assistant_only',
    message: 'Introduce this lesson simply.',
  }).expect(200);

  assert.equal(forwardedBody.history_mode, 'assistant_only');
});
