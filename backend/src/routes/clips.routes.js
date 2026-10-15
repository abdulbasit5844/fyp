const fs = require('fs');
const path = require('path');
const express = require('express');
const { VideoClip } = require('../models');
const config = require('../config');
const ApiError = require('../utils/ApiError');

const router = express.Router();

router.get('/:id', async (req, res) => {
  const clip = await VideoClip.findOne({ _id: req.params.id, owner: req.ownerId });
  if (!clip) throw ApiError.notFound('Clip not found');
  res.json(clip);
});

// FR7.2 / SEC-4 – authenticated streaming with HTTP Range support so video
// players can seek.
router.get('/:id/stream', async (req, res) => {
  const clip = await VideoClip.findOne({ _id: req.params.id, owner: req.ownerId });
  if (!clip || clip.status !== 'available') throw ApiError.notFound('Clip is not available');

  const filePath = path.resolve(clip.filePath);
  const root = path.resolve(config.clipsDir) + path.sep;
  if (!filePath.startsWith(root)) throw ApiError.forbidden('Clip is outside the clips folder');

  let stat;
  try {
    stat = await fs.promises.stat(filePath);
  } catch {
    throw ApiError.notFound('Clip file is missing on the device');
  }

  const range = req.get('range');
  res.set({ 'Content-Type': clip.mimeType, 'Accept-Ranges': 'bytes' });

  if (!range) {
    res.set('Content-Length', stat.size);
    return fs.createReadStream(filePath).pipe(res);
  }

  const match = /bytes=(\d*)-(\d*)/.exec(range);
  let start = match && match[1] ? parseInt(match[1], 10) : 0;
  let end = match && match[2] ? parseInt(match[2], 10) : stat.size - 1;
  if (match && !match[1] && match[2]) { // suffix range: last N bytes
    start = Math.max(0, stat.size - parseInt(match[2], 10));
    end = stat.size - 1;
  }
  if (!match || start > end || end >= stat.size) {
    res.set('Content-Range', `bytes */${stat.size}`);
    return res.status(416).end();
  }

  res.status(206).set({
    'Content-Range': `bytes ${start}-${end}/${stat.size}`,
    'Content-Length': end - start + 1,
  });
  return fs.createReadStream(filePath, { start, end }).pipe(res);
});

module.exports = router;
