/* Shared timing helper; also exercised with Node without a browser. */
function sampleFrame(seconds, frameTime, count, loop = true) {
  const duration = frameTime * count;
  const time = loop ? ((seconds % duration) + duration) % duration : Math.max(0, seconds);
  return Math.min(Math.floor(time / frameTime + 1e-10), count - 1);
}
if (typeof module !== 'undefined') module.exports = { sampleFrame };
