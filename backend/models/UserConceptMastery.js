import mongoose from 'mongoose';

const userConceptMasterySchema = new mongoose.Schema(
  {
    userId: { type: String, required: true, index: true },
    chapterName: { type: String, required: true },
    lessonName: { type: String, required: true },
    normalizedChapterName: { type: String, required: true },
    normalizedLessonName: { type: String, required: true },
    questionAttempts: { type: Number, default: 0 },
    correctAnswers: { type: Number, default: 0 },
    wrongAnswers: { type: Number, default: 0 },
    chatConfusionCount: { type: Number, default: 0 },
    lessonTimeSeconds: { type: Number, default: 0 },
    masteryScore: { type: Number, default: 0 },
    lastActivityAt: { type: Date, default: null },
    lastExamAt: { type: Date, default: null },
    lastLessonSeenAt: { type: Date, default: null },
  },
  { timestamps: true },
);

userConceptMasterySchema.index(
  { userId: 1, normalizedChapterName: 1, normalizedLessonName: 1 },
  { unique: true },
);

const UserConceptMastery = mongoose.models.UserConceptMastery
  || mongoose.model('UserConceptMastery', userConceptMasterySchema);

export default UserConceptMastery;
