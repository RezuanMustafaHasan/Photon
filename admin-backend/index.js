const cors = require('cors');
const dotenv = require('dotenv');
const express = require('express');
const fs = require('fs/promises');
const path = require('path');
const mongoose = require('mongoose');
const multer = require('multer');
const { v2: cloudinary } = require('cloudinary');

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5050;
const USERS_FILE = path.join(__dirname, 'db', 'users.json');
const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/hsc_physics_db';
const MAIN_COLLECTION = 'main_book';
const MAIN_DOC_ID = 'main_book';
const CLOUDINARY_CLOUD_NAME = process.env.CLOUDINARY_CLOUD_NAME || '';
const CLOUDINARY_API_KEY = process.env.CLOUDINARY_API_KEY || '';
const CLOUDINARY_API_SECRET = process.env.CLOUDINARY_API_SECRET || '';
const CLOUDINARY_FOLDER = process.env.CLOUDINARY_FOLDER || 'photon/lesson-images';

const jsonUpload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 15 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (path.extname(file.originalname).toLowerCase() !== '.json') {
      return cb(new Error('Only .json files are allowed'));
    }
    cb(null, true);
  },
});

const imageUpload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 15 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (!file.mimetype || !file.mimetype.startsWith('image/')) {
      return cb(new Error('Only image files are allowed'));
    }
    cb(null, true);
  },
});

if (CLOUDINARY_CLOUD_NAME && CLOUDINARY_API_KEY && CLOUDINARY_API_SECRET) {
  cloudinary.config({
    cloud_name: CLOUDINARY_CLOUD_NAME,
    api_key: CLOUDINARY_API_KEY,
    api_secret: CLOUDINARY_API_SECRET,
  });
}

app.use(cors());
app.use(express.json({ limit: '10mb' }));

let connectPromise;

const connectMongo = () => {
  if (!connectPromise) {
    connectPromise = mongoose.connect(MONGODB_URI);
  }
  return connectPromise;
};

const getDb = async () => {
  await connectMongo();
  return mongoose.connection.db;
};

const ensureDirectory = async (dirPath) => {
  await fs.mkdir(dirPath, { recursive: true });
};

const ensureSeedFiles = async () => {
  await ensureDirectory(path.dirname(USERS_FILE));
  try {
    await fs.access(USERS_FILE);
  } catch (error) {
    const seedUsers = [
      { id: 'u-001', name: 'Admin Demo', email: 'admin@example.com', role: 'admin' },
      { id: 'u-002', name: 'Student Demo', email: 'student@example.com', role: 'student' },
    ];
    await fs.writeFile(USERS_FILE, JSON.stringify(seedUsers, null, 2), 'utf8');
  }
};

const getMainCollection = async () => {
  const db = await getDb();
  return db.collection(MAIN_COLLECTION);
};

const ensureMainDoc = async () => {
  const collection = await getMainCollection();
  await collection.updateOne(
    { _id: MAIN_DOC_ID },
    { $setOnInsert: { _id: MAIN_DOC_ID, items: [] } },
    { upsert: true },
  );
  return collection;
};

const loadMainItems = async () => {
  const collection = await ensureMainDoc();
  const doc = await collection.findOne({ _id: MAIN_DOC_ID });
  return Array.isArray(doc?.items) ? doc.items : [];
};

const writeMainItems = async (items) => {
  const collection = await ensureMainDoc();
  await collection.updateOne(
    { _id: MAIN_DOC_ID },
    { $set: { items } },
  );
};

const normalizeFileName = (input) => {
  if (!input || typeof input !== 'string') {
    throw new Error('File name is required');
  }
  const fileName = path.basename(input);
  if (!fileName || path.extname(fileName).toLowerCase() !== '.json') {
    throw new Error('Only .json files are allowed');
  }
  return fileName;
};

const normalizeText = (value) => String(value || '').trim().toLowerCase();

const parseTopics = (input) => {
  if (Array.isArray(input)) {
    return input.map((value) => String(value).trim()).filter(Boolean);
  }

  if (typeof input !== 'string') {
    return [];
  }

  const trimmed = input.trim();
  if (!trimmed) {
    return [];
  }

  try {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed)) {
      return parsed.map((value) => String(value).trim()).filter(Boolean);
    }
  } catch {
    // Fall back to comma-separated text.
  }

  return trimmed
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
};

const getChapterSource = (item) => {
  if (item?.content && typeof item.content === 'object') {
    return item.content;
  }
  return item;
};

const getChapterId = (item) => {
  const source = getChapterSource(item);
  return item?.name || source?.chapter_name || source?.chapter_name_bn || '';
};

const getChapterDisplayName = (item) => {
  const source = getChapterSource(item);
  return source?.chapter_name_bn || source?.chapter_name || item?.name || '';
};

const getLessonDisplayName = (lesson) => {
  return lesson?.lesson_name || lesson?.lesson_name_bn || lesson?.lesson_title || '';
};

const findChapterById = (items, chapterId) => {
  const targetId = normalizeText(chapterId);
  return items.find((item) => normalizeText(getChapterId(item)) === targetId);
};

const findLessonByName = (lessons, lessonName) => {
  const targetName = normalizeText(lessonName);
  return lessons.find((lesson) => normalizeText(getLessonDisplayName(lesson)) === targetName);
};

const isCloudinaryConfigured = () => {
  return Boolean(CLOUDINARY_CLOUD_NAME && CLOUDINARY_API_KEY && CLOUDINARY_API_SECRET);
};

const normalizePublicId = (fileName) => {
  const baseName = path.parse(String(fileName || 'lesson-image')).name;
  return baseName.replace(/[^a-zA-Z0-9_-]+/g, '-').replace(/^-+|-+$/g, '') || `lesson-image-${Date.now()}`;
};

const serializeImageRecord = (image, index) => ({
  index,
  imageURL: String(image?.imageURL || '').trim(),
  description: String(image?.description || '').trim(),
  topic: parseTopics(image?.topic),
  publicId: String(image?.publicId || '').trim(),
});

const parseImageIndex = (value) => {
  const parsed = Number.parseInt(String(value ?? ''), 10);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error('imageIndex must be a non-negative integer');
  }
  return parsed;
};

const getLessonContext = (items, chapterId, lessonName) => {
  const chapter = findChapterById(items, chapterId);
  if (!chapter) {
    return { error: 'Chapter not found' };
  }

  const source = getChapterSource(chapter);
  if (!Array.isArray(source?.lessons)) {
    return { error: 'No lessons found for chapter' };
  }

  const lesson = findLessonByName(source.lessons, lessonName);
  if (!lesson) {
    return { error: 'Lesson not found' };
  }

  if (!Array.isArray(lesson.images)) {
    lesson.images = [];
  }

  return { chapter, lesson };
};

const uploadImageToCloudinary = (buffer, originalName) => {
  return new Promise((resolve, reject) => {
    const uploadStream = cloudinary.uploader.upload_stream(
      {
        folder: CLOUDINARY_FOLDER,
        resource_type: 'image',
        public_id: `${Date.now()}-${normalizePublicId(originalName)}`,
      },
      (error, result) => {
        if (error) {
          reject(error);
          return;
        }
        resolve(result);
      },
    );

    uploadStream.end(buffer);
  });
};

const deleteImageFromCloudinary = async (publicId) => {
  if (!publicId || !isCloudinaryConfigured()) {
    return null;
  }

  return cloudinary.uploader.destroy(publicId, { resource_type: 'image' });
};

app.get('/api/admin/users', async (req, res) => {
  try {
    const data = await fs.readFile(USERS_FILE, 'utf8');
    const users = JSON.parse(data);
    res.json({ users });
  } catch (error) {
    res.status(500).json({ message: 'Failed to load users' });
  }
});

app.get('/api/admin/contents/directories', async (req, res) => {
  try {
    res.json({ directories: [] });
  } catch (error) {
    res.status(500).json({ message: 'Failed to load directories' });
  }
});

app.get('/api/admin/contents/list', async (req, res) => {
  try {
    const items = await loadMainItems();
    const files = items.map((item) => item.name).filter(Boolean).sort();
    res.json({ directories: [], files });
  } catch (error) {
    res.status(400).json({ message: 'Failed to list directory' });
  }
});

app.post('/api/admin/contents/directory', async (req, res) => {
  try {
    await ensureMainDoc();
    res.json({ message: 'Collection ready' });
  } catch (error) {
    res.status(400).json({ message: 'Failed to prepare collection' });
  }
});

app.post('/api/admin/contents/upload', jsonUpload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ message: 'No file provided' });
    }
    const safeName = normalizeFileName(req.file.originalname);
    let content;
    try {
      content = JSON.parse(req.file.buffer.toString('utf8'));
    } catch (parseError) {
      return res.status(400).json({ message: 'Invalid JSON file' });
    }
    const items = await loadMainItems();
    const existingIndex = items.findIndex((item) => item.name === safeName);
    const now = new Date();
    if (existingIndex >= 0) {
      items[existingIndex] = { ...items[existingIndex], name: safeName, content, updatedAt: now };
    } else {
      items.push({ name: safeName, content, createdAt: now, updatedAt: now });
    }
    await writeMainItems(items);
    res.json({ message: 'File uploaded', fileName: safeName });
  } catch (error) {
    res.status(400).json({ message: 'Failed to upload file' });
  }
});

app.get('/api/admin/images/chapters', async (req, res) => {
  try {
    const items = await loadMainItems();
    const chapters = items
      .map((item) => ({
        id: getChapterId(item),
        name: getChapterDisplayName(item),
      }))
      .filter((chapter) => chapter.id && chapter.name)
      .sort((a, b) => a.name.localeCompare(b.name));

    res.json({ chapters });
  } catch {
    res.status(500).json({ message: 'Failed to load chapters' });
  }
});

app.get('/api/admin/images/lessons', async (req, res) => {
  try {
    const chapterId = req.query.chapterId;
    if (!chapterId) {
      return res.status(400).json({ message: 'chapterId is required' });
    }

    const items = await loadMainItems();
    const chapter = findChapterById(items, chapterId);
    if (!chapter) {
      return res.status(404).json({ message: 'Chapter not found' });
    }

    const source = getChapterSource(chapter);
    const lessons = Array.isArray(source?.lessons)
      ? source.lessons.map((lesson) => getLessonDisplayName(lesson)).filter(Boolean)
      : [];

    res.json({ lessons });
  } catch {
    res.status(500).json({ message: 'Failed to load lessons' });
  }
});

app.get('/api/admin/images/lesson', async (req, res) => {
  try {
    const chapterId = String(req.query.chapterId || '').trim();
    const lessonName = String(req.query.lessonName || '').trim();

    if (!chapterId || !lessonName) {
      return res.status(400).json({ message: 'chapterId and lessonName are required' });
    }

    const items = await loadMainItems();
    const { chapter, lesson, error } = getLessonContext(items, chapterId, lessonName);

    if (error) {
      const statusCode = error.includes('not found') ? 404 : 400;
      return res.status(statusCode).json({ message: error });
    }

    const images = lesson.images.map((image, index) => serializeImageRecord(image, index));

    res.json({
      chapter: getChapterDisplayName(chapter),
      lesson: getLessonDisplayName(lesson),
      images,
    });
  } catch {
    res.status(500).json({ message: 'Failed to load lesson images' });
  }
});

app.post('/api/admin/images/upload', imageUpload.single('image'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ message: 'Image file is required' });
    }

    if (!isCloudinaryConfigured()) {
      return res.status(500).json({
        message: 'Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.',
      });
    }

    const chapterId = String(req.body.chapterId || '').trim();
    const lessonName = String(req.body.lessonName || '').trim();
    const description = String(req.body.description || '').trim();
    const topic = parseTopics(req.body.topics);

    if (!chapterId || !lessonName) {
      return res.status(400).json({ message: 'chapterId and lessonName are required' });
    }

    if (!description) {
      return res.status(400).json({ message: 'description is required' });
    }

    if (!topic.length) {
      return res.status(400).json({ message: 'At least one topic is required' });
    }

    const uploadResult = await uploadImageToCloudinary(req.file.buffer, req.file.originalname);
    const imageURL = uploadResult?.secure_url || uploadResult?.url;

    if (!imageURL) {
      return res.status(500).json({ message: 'Cloudinary upload did not return an image URL' });
    }

    const items = await loadMainItems();
    const { chapter, lesson, error } = getLessonContext(items, chapterId, lessonName);
    if (error) {
      return res.status(404).json({ message: error });
    }

    const imageRecord = {
      imageURL,
      description,
      topic,
      publicId: String(uploadResult?.public_id || '').trim(),
    };

    lesson.images.push(imageRecord);
    await writeMainItems(items);

    res.status(201).json({
      message: 'Image uploaded and lesson updated',
      image: imageRecord,
      chapter: getChapterDisplayName(chapter),
      lesson: getLessonDisplayName(lesson),
    });
  } catch {
    res.status(400).json({ message: 'Failed to upload image and update lesson' });
  }
});

app.put('/api/admin/images/item', imageUpload.single('image'), async (req, res) => {
  let replacementPublicId = '';

  try {
    const chapterId = String(req.body.chapterId || '').trim();
    const lessonName = String(req.body.lessonName || '').trim();
    const description = String(req.body.description || '').trim();
    const topic = parseTopics(req.body.topics);
    const imageIndex = parseImageIndex(req.body.imageIndex);

    if (!chapterId || !lessonName) {
      return res.status(400).json({ message: 'chapterId and lessonName are required' });
    }

    if (!description) {
      return res.status(400).json({ message: 'description is required' });
    }

    if (!topic.length) {
      return res.status(400).json({ message: 'At least one topic is required' });
    }

    const items = await loadMainItems();
    const { chapter, lesson, error } = getLessonContext(items, chapterId, lessonName);
    if (error) {
      return res.status(404).json({ message: error });
    }

    const existingImage = lesson.images[imageIndex];
    if (!existingImage) {
      return res.status(404).json({ message: 'Image not found' });
    }

    let imageURL = String(existingImage.imageURL || '').trim();
    let publicId = String(existingImage.publicId || '').trim();

    if (req.file) {
      if (!isCloudinaryConfigured()) {
        return res.status(500).json({
          message: 'Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.',
        });
      }

      const uploadResult = await uploadImageToCloudinary(req.file.buffer, req.file.originalname);
      replacementPublicId = String(uploadResult?.public_id || '').trim();
      imageURL = uploadResult?.secure_url || uploadResult?.url || '';
      publicId = replacementPublicId || publicId;

      if (!imageURL) {
        throw new Error('Cloudinary upload did not return an image URL');
      }
    }

    const previousPublicId = String(existingImage.publicId || '').trim();

    lesson.images[imageIndex] = {
      ...existingImage,
      imageURL,
      description,
      topic,
      ...(publicId ? { publicId } : {}),
    };

    await writeMainItems(items);

    if (req.file && previousPublicId && previousPublicId !== publicId) {
      await deleteImageFromCloudinary(previousPublicId).catch(() => null);
    }

    res.json({
      message: 'Image updated',
      chapter: getChapterDisplayName(chapter),
      lesson: getLessonDisplayName(lesson),
      image: serializeImageRecord(lesson.images[imageIndex], imageIndex),
    });
  } catch (error) {
    if (replacementPublicId) {
      await deleteImageFromCloudinary(replacementPublicId).catch(() => null);
    }
    res.status(400).json({ message: error.message || 'Failed to update image' });
  }
});

app.delete('/api/admin/images/item', async (req, res) => {
  try {
    const chapterId = String(req.query.chapterId || req.body?.chapterId || '').trim();
    const lessonName = String(req.query.lessonName || req.body?.lessonName || '').trim();
    const imageIndex = parseImageIndex(req.query.imageIndex || req.body?.imageIndex);

    if (!chapterId || !lessonName) {
      return res.status(400).json({ message: 'chapterId and lessonName are required' });
    }

    const items = await loadMainItems();
    const { chapter, lesson, error } = getLessonContext(items, chapterId, lessonName);
    if (error) {
      return res.status(404).json({ message: error });
    }

    const existingImage = lesson.images[imageIndex];
    if (!existingImage) {
      return res.status(404).json({ message: 'Image not found' });
    }

    const [removedImage] = lesson.images.splice(imageIndex, 1);
    await writeMainItems(items);

    let warning = '';
    const removedPublicId = String(removedImage?.publicId || '').trim();
    if (removedPublicId) {
      try {
        await deleteImageFromCloudinary(removedPublicId);
      } catch {
        warning = 'Image entry was deleted, but Cloudinary cleanup failed.';
      }
    }

    res.json({
      message: warning || 'Image deleted',
      warning,
      chapter: getChapterDisplayName(chapter),
      lesson: getLessonDisplayName(lesson),
      image: serializeImageRecord(removedImage, imageIndex),
      remainingImages: lesson.images.length,
    });
  } catch (error) {
    res.status(400).json({ message: error.message || 'Failed to delete image' });
  }
});

app.get('/api/admin/contents/file', async (req, res) => {
  try {
    const fileName = normalizeFileName(req.query.path || '');
    const items = await loadMainItems();
    const item = items.find((entry) => entry.name === fileName);
    if (!item) {
      return res.status(404).json({ message: 'File not found' });
    }
    res.json({ content: item.content });
  } catch (error) {
    res.status(400).json({ message: 'Failed to read file' });
  }
});

app.put('/api/admin/contents/file', async (req, res) => {
  try {
    const fileName = normalizeFileName(req.body.path || '');
    const content = req.body.content;
    let json;
    if (typeof content === 'string') {
      json = JSON.parse(content);
    } else {
      json = content;
    }
    const items = await loadMainItems();
    const existingIndex = items.findIndex((item) => item.name === fileName);
    if (existingIndex < 0) {
      return res.status(404).json({ message: 'File not found' });
    }
    items[existingIndex] = { ...items[existingIndex], name: fileName, content: json, updatedAt: new Date() };
    await writeMainItems(items);
    res.json({ message: 'File updated' });
  } catch (error) {
    res.status(400).json({ message: 'Failed to update file' });
  }
});

app.use((err, req, res, next) => {
  if (err) {
    res.status(400).json({ message: err.message || 'Request failed' });
    return;
  }
  next();
});

ensureSeedFiles()
  .then(connectMongo)
  .then(() => {
    app.listen(PORT, () => {
      console.log(`Admin backend running on http://localhost:${PORT}`);
    });
  })
  .catch((error) => {
    console.error('Failed to start admin backend:', error.message);
    process.exit(1);
  });
