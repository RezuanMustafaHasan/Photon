import mongoose from 'mongoose';

const connectDB = async (mongoUri) => {
  if (!mongoUri) {
    throw new Error('MONGO_URI is required');
  }
  await mongoose.connect(mongoUri);
};

export default connectDB;

