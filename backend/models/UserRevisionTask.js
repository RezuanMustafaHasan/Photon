import mongoose from 'mongoose';

const userRevisionTaskSchema = new mongoose.Schema(
  {
    userId: { type: String, required: true, index: true },
    chapterName: { type: String, required: true },
    lessonName: { type: String, required: true },
    normalizedChapterName: { type: String, required: true },
    normalizedLessonName: { type: String, required: true },
    masteryScore: { type: Number, default: 0 },
    dueAt: { type: Date, required: true, index: true },
    intervalDays: { type: Number, default: 1 },
    easeLevel: { type: Number, default: 2.5 },
    status: { type: String, enum: ['active'], default: 'active', index: true },
    lastReviewedAt: { type: Date, default: null },
    reviewCount: { type: Number, default: 0 },
    lapseCount: { type: Number, default: 0 },
    source: { type: String, default: 'mastery' },
    reason: { type: String, default: '' },
  },
  { timestamps: true },
);

userRevisionTaskSchema.index(
  { userId: 1, normalizedChapterName: 1, normalizedLessonName: 1 },
  { unique: true },
);

const UserRevisionTask = mongoose.models.UserRevisionTask
  || mongoose.model('UserRevisionTask', userRevisionTaskSchema);

export default UserRevisionTask;
