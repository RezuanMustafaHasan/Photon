import mongoose from 'mongoose';

const examAttemptSchema = new mongoose.Schema(
  {
    userId: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true, index: true },
    selections: { type: [mongoose.Schema.Types.Mixed], default: [] },
    questionCount: { type: Number, required: true },
    questions: { type: [mongoose.Schema.Types.Mixed], default: [] },
    answers: { type: Map, of: Number, default: {} },
    score: { type: Number, required: true },
    percentage: { type: Number, required: true },
    scoreComment: { type: String, required: true },
    wrongQuestions: { type: [mongoose.Schema.Types.Mixed], default: [] },
    aiSummary: { type: mongoose.Schema.Types.Mixed, required: true },
  },
  { timestamps: true },
);

const ExamAttempt = mongoose.models.ExamAttempt || mongoose.model('ExamAttempt', examAttemptSchema);

export default ExamAttempt;
