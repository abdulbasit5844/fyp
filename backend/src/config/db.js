const mongoose = require('mongoose');
const config = require('./index');

async function connectDB() {
  mongoose.set('strictQuery', true);
  await mongoose.connect(config.mongoUri, { serverSelectionTimeoutMS: 5000 });
  // Build indexes declared on the schemas (unique email, contact limits, etc.).
  await mongoose.syncIndexes();
  console.log(`[db] connected to ${mongoose.connection.name}`);
}

module.exports = connectDB;
