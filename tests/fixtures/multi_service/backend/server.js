const express = require('express');
const axios = require('axios');
const app = express();
const port = process.env.PORT || 4000;

app.get('/health', async (req, res) => {
  const response = await axios.get(process.env.CUSTOM_API_ENDPOINT || 'http://internal:8080');
  res.json({ ok: response.status });
});

app.listen(port, () => console.log('Listening on', port));
