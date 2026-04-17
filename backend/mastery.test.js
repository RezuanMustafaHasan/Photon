import assert from 'node:assert/strict';
import test from 'node:test';
import jwt from 'jsonwebtoken';
import mongoose from 'mongoose';
import request from 'supertest';
import { MongoMemoryServer } from 'mongodb-memory-server';
import { createApp } from './app.js';

const JWT_SECRET = 'dev_secret_change_me';
const originalFetch = global.fetch;

const createToken = (userId) => jwt.sign({ sub: userId }, JWT_SECRET, { expiresIn: '1h' });

const buildSyllabus = (chapters) => ({
  _id: 'main_book',
  items: chapters.map((chapter) => ({
    content: {
      chapter_name: chapter.chapterNameEn || chapter.chapterName,
      chapter_name_bn: chapter.chapterName,
      lessons: chapter.lessons.map((lessonName) => ({
        lesson_name: lessonName,
      })),
    },
  })),
});

const connectMemoryDb = async (chapters) => {
  const server = await MongoMemoryServer.create();
  await mongoose.connect(server.getUri(), {
    dbName: 'photon_test',
  });

  await mongoose.connection.db.collection('main_book').replaceOne(
    { _id: 'main_book' },
    buildSyllabus(chapters),
    { upsert: true },
  );

  return server;
};

const disconnectMemoryDb = async (server) => {
  await mongoose.connection.dropDatabase();
  await mongoose.disconnect();
  await server.stop();
};

test('mastery summary works for a brand-new user with live syllabus data', async (t) => {
  const mongoServer = await connectMemoryDb([
    { chapterName: 'Static Electricity', lessons: ['আধান', 'তড়িৎ ক্ষেত্র'] },
    { chapterName: 'নিউটনের বলবিদ্যা', lessons: ['টর্ক (Torque)'] },
  ]);
  t.after(async () => {
    await disconnectMemoryDb(mongoServer);
  });

  const app = createApp({
    rateLimit: {
      enabled: false,
      redisClient: null,
    },
  });
  const token = createToken('507f1f77bcf86cd799439011');

  const response = await request(app)
    .get('/api/mastery/summary')
    .set('Authorization', `Bearer ${token}`)
    .expect(200);

  assert.equal(response.body.overallProgress, 0);
  assert.equal(response.body.practicedLessons, 0);
  assert.equal(response.body.totalLessons, 3);
  assert.equal(response.body.chapterProgress.length, 2);
  assert.equal(response.body.chapterProgress[0].chapterName, 'Static Electricity');
  assert.equal(response.body.chapterProgress[1].chapterName, 'নিউটনের বলবিদ্যা');
});

test('mastery summary picks up newly added chapters without code changes', async (t) => {
  const mongoServer = await connectMemoryDb([
    { chapterName: 'Static Electricity', lessons: ['আধান'] },
  ]);
  t.after(async () => {
    await disconnectMemoryDb(mongoServer);
  });

  const app = createApp({
    rateLimit: {
      enabled: false,
      redisClient: null,
    },
  });
  const token = createToken('507f1f77bcf86cd799439012');

  await request(app)
    .post('/api/mastery/lesson-activity')
    .set('Authorization', `Bearer ${token}`)
    .send({
      chapterName: 'Static Electricity',
      lessonName: 'আধান',
      seconds: 30,
    })
    .expect(202);

  await mongoose.connection.db.collection('main_book').replaceOne(
    { _id: 'main_book' },
    buildSyllabus([
      { chapterName: 'Static Electricity', lessons: ['আধান'] },
      { chapterName: 'Gravitation', lessons: ['মহাকর্ষ'] },
    ]),
    { upsert: true },
  );

  const response = await request(app)
    .get('/api/mastery/summary')
    .set('Authorization', `Bearer ${token}`)
    .expect(200);

  assert.equal(response.body.totalLessons, 2);
  assert.equal(response.body.chapterProgress.length, 2);
  assert.ok(response.body.chapterProgress.some((chapter) => chapter.chapterName === 'Gravitation' && chapter.masteryScore === 0));
});

test('exam completion and chat confusion both feed lesson mastery signals', async (t) => {
  const mongoServer = await connectMemoryDb([
    { chapterName: 'Static Electricity', lessons: ['ধারকের শক্তি', 'তড়িৎ ক্ষেত্র'] },
  ]);
  t.after(async () => {
    global.fetch = originalFetch;
    await disconnectMemoryDb(mongoServer);
  });

  global.fetch = async (url) => {
    if (String(url).includes('/exam/analyze')) {
      return new Response(JSON.stringify({
        summary: {
          headline: 'Done',
          overallComment: 'Done',
          weaknesses: [],
          recommendedTopics: [],
          studyAdvice: [],
        },
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify({
      response: '**From your lesson**\n\nআবার দেখি।',
      textbook_answer: 'আবার দেখি।',
      extra_explanation: 'সহজ করে বলছি।',
      citations: [],
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  const app = createApp({
    rateLimit: {
      enabled: false,
      redisClient: null,
    },
  });
  const token = createToken('507f1f77bcf86cd799439013');

  await request(app)
    .post('/api/exams/complete')
    .set('Authorization', `Bearer ${token}`)
    .send({
      selections: [
        {
          chapterName: 'Static Electricity',
          topicNames: ['ধারকের শক্তি'],
        },
      ],
      questionCount: 1,
      questions: [
        {
          id: 'q1',
          chapterName: 'Static Electricity',
          topicName: 'ধারকের শক্তি',
          question: 'Energy formula?',
          options: ['A', 'B', 'C', 'D'],
          correctOptionIndex: 1,
        },
      ],
      answers: {
        q1: 0,
      },
    })
    .expect(201);

  await request(app)
    .post('/api/chat')
    .set('Authorization', `Bearer ${token}`)
    .send({
      message: 'বোঝিনি, সহজ করে বুঝাও',
      chapterName: 'Static Electricity',
      lessonName: 'তড়িৎ ক্ষেত্র',
    })
    .expect(200);

  const response = await request(app)
    .get('/api/mastery/summary')
    .set('Authorization', `Bearer ${token}`)
    .expect(200);

  assert.equal(response.body.practicedLessons, 2);
  assert.equal(response.body.weakConcepts.length, 2);
  assert.ok(response.body.weakConcepts.some((concept) => concept.lessonName === 'ধারকের শক্তি'));
  assert.ok(response.body.weakConcepts.some((concept) => concept.lessonName === 'তড়িৎ ক্ষেত্র'));
  assert.equal(response.body.recommendedExam.chapterName, 'Static Electricity');
});

test('exam completion forwards the selected exam model to the analysis service', async (t) => {
  const mongoServer = await connectMemoryDb([
    { chapterName: 'Static Electricity', lessons: ['তড়িৎ ক্ষেত্র'] },
  ]);
  let forwardedBody = null;

  t.after(async () => {
    global.fetch = originalFetch;
    await disconnectMemoryDb(mongoServer);
  });

  global.fetch = async (url, init) => {
    if (String(url).includes('/exam/analyze')) {
      forwardedBody = JSON.parse(init.body);
      return new Response(JSON.stringify({
        summary: {
          headline: 'Done',
          overallComment: 'Done',
          weaknesses: [],
          recommendedTopics: [],
          studyAdvice: [],
        },
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    throw new Error(`Unexpected upstream URL: ${url}`);
  };

  const app = createApp({
    rateLimit: {
      enabled: false,
      redisClient: null,
    },
  });
  const token = createToken('507f1f77bcf86cd799439014');

  await request(app)
    .post('/api/exams/complete')
    .set('Authorization', `Bearer ${token}`)
    .send({
      selections: [
        {
          chapterName: 'Static Electricity',
          topicNames: ['তড়িৎ ক্ষেত্র'],
        },
      ],
      questionCount: 1,
      questions: [
        {
          id: 'q1',
          chapterName: 'Static Electricity',
          topicName: 'তড়িৎ ক্ষেত্র',
          question: 'What is electric field?',
          options: ['A', 'B', 'C', 'D'],
          correctOptionIndex: 1,
        },
      ],
      answers: {
        q1: 0,
      },
      examModel: 'openai:gpt-4.1-mini',
    })
    .expect(201);

  assert.equal(forwardedBody.exam_model, 'openai:gpt-4.1-mini');
});
