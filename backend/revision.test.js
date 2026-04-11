import assert from 'node:assert/strict';
import test from 'node:test';
import jwt from 'jsonwebtoken';
import mongoose from 'mongoose';
import request from 'supertest';
import { MongoMemoryServer } from 'mongodb-memory-server';
import { createApp } from './app.js';
import UserConceptMastery from './models/UserConceptMastery.js';
import UserRevisionTask from './models/UserRevisionTask.js';

const JWT_SECRET = 'dev_secret_change_me';

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
    dbName: 'photon_revision_test',
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

test('revision queue creates due tasks from weak live mastery lessons and refreshes idempotently', async (t) => {
  const mongoServer = await connectMemoryDb([
    { chapterName: 'Static Electricity', lessons: ['ধারকের শক্তি'] },
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
  const token = createToken('507f1f77bcf86cd799439021');

  await request(app)
    .post('/api/mastery/lesson-activity')
    .set('Authorization', `Bearer ${token}`)
    .send({
      chapterName: 'Static Electricity',
      lessonName: 'ধারকের শক্তি',
      seconds: 45,
    })
    .expect(202);

  await request(app)
    .post('/api/revision/refresh')
    .set('Authorization', `Bearer ${token}`)
    .expect(202);
  await request(app)
    .post('/api/revision/refresh')
    .set('Authorization', `Bearer ${token}`)
    .expect(202);

  const response = await request(app)
    .get('/api/revision/today')
    .set('Authorization', `Bearer ${token}`)
    .expect(200);

  assert.equal(response.body.dueCount, 1);
  assert.equal(response.body.tasks.length, 1);
  assert.equal(response.body.tasks[0].chapterName, 'Static Electricity');
  assert.equal(response.body.tasks[0].lessonName, 'ধারকের শক্তি');
  assert.equal(await UserRevisionTask.countDocuments({ userId: '507f1f77bcf86cd799439021' }), 1);
});

test('revision queue ignores mastery rows for lessons not present in the live syllabus', async (t) => {
  const mongoServer = await connectMemoryDb([
    { chapterName: 'Static Electricity', lessons: ['আধান'] },
  ]);
  t.after(async () => {
    await disconnectMemoryDb(mongoServer);
  });

  await UserConceptMastery.create({
    userId: '507f1f77bcf86cd799439022',
    chapterName: 'Ghost Chapter',
    lessonName: 'Ghost Lesson',
    normalizedChapterName: 'ghost chapter',
    normalizedLessonName: 'ghost lesson',
    questionAttempts: 2,
    correctAnswers: 0,
    wrongAnswers: 2,
    masteryScore: 0,
    lastActivityAt: new Date(),
  });

  const app = createApp({
    rateLimit: {
      enabled: false,
      redisClient: null,
    },
  });
  const token = createToken('507f1f77bcf86cd799439022');

  const response = await request(app)
    .get('/api/revision/today')
    .set('Authorization', `Bearer ${token}`)
    .expect(200);

  assert.equal(response.body.dueCount, 0);
  assert.equal(await UserRevisionTask.countDocuments({ userId: '507f1f77bcf86cd799439022' }), 0);
});

test('new syllabus lessons become eligible for revision after mastery signals are added', async (t) => {
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
  const token = createToken('507f1f77bcf86cd799439023');

  await mongoose.connection.db.collection('main_book').replaceOne(
    { _id: 'main_book' },
    buildSyllabus([
      { chapterName: 'Static Electricity', lessons: ['আধান'] },
      { chapterName: 'Gravitation', lessons: ['মহাকর্ষ'] },
    ]),
    { upsert: true },
  );

  await request(app)
    .post('/api/mastery/lesson-activity')
    .set('Authorization', `Bearer ${token}`)
    .send({
      chapterName: 'Gravitation',
      lessonName: 'মহাকর্ষ',
      seconds: 60,
    })
    .expect(202);

  const response = await request(app)
    .get('/api/revision/today')
    .set('Authorization', `Bearer ${token}`)
    .expect(200);

  assert.equal(response.body.dueCount, 1);
  assert.equal(response.body.tasks[0].chapterName, 'Gravitation');
  assert.equal(response.body.tasks[0].lessonName, 'মহাকর্ষ');
});

test('review outcomes move tasks into the future and update spacing metadata', async (t) => {
  const mongoServer = await connectMemoryDb([
    { chapterName: 'Static Electricity', lessons: ['তড়িৎ ক্ষেত্র'] },
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
  const token = createToken('507f1f77bcf86cd799439024');

  await request(app)
    .post('/api/mastery/lesson-activity')
    .set('Authorization', `Bearer ${token}`)
    .send({
      chapterName: 'Static Electricity',
      lessonName: 'তড়িৎ ক্ষেত্র',
      seconds: 30,
    })
    .expect(202);

  const today = await request(app)
    .get('/api/revision/today')
    .set('Authorization', `Bearer ${token}`)
    .expect(200);

  const taskId = today.body.tasks[0].id;
  const reviewed = await request(app)
    .post(`/api/revision/${taskId}/review`)
    .set('Authorization', `Bearer ${token}`)
    .send({ outcome: 'good' })
    .expect(200);

  assert.equal(reviewed.body.task.reviewCount, 1);
  assert.equal(reviewed.body.task.lapseCount, 0);

  const savedTask = await UserRevisionTask.findById(taskId).lean();
  assert.ok(savedTask.intervalDays >= 4);
  assert.ok(new Date(savedTask.dueAt).getTime() > Date.now() + (3 * 24 * 60 * 60 * 1000));

  const afterReview = await request(app)
    .get('/api/revision/today')
    .set('Authorization', `Bearer ${token}`)
    .expect(200);

  assert.equal(afterReview.body.dueCount, 0);
  assert.ok(afterReview.body.nextDueAt);
});
