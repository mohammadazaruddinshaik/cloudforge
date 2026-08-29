const express = require('express');
const mongoose = require('mongoose');
const app = express();

const port = process.env.PORT || 5000;

mongoose.connect(process.env.MONGO_URI || 'mongodb://localhost:27017/app');

app.listen(port, () => {
  console.log('Backend listening on', port);
});
