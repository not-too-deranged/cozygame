let ctx = null;
function ac() {
  if (typeof window === "undefined") return null;
  if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === "suspended") ctx.resume();
  return ctx;
}

function tone(freq, dur = 0.09, type = "sine", gain = 0.06) {
  const c = ac();
  if (!c) return;
  const osc = c.createOscillator();
  const g = c.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  g.gain.setValueAtTime(gain, c.currentTime);
  g.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + dur);
  osc.connect(g);
  g.connect(c.destination);
  osc.start();
  osc.stop(c.currentTime + dur);
}

export const sfx = {
  click: () => tone(520, 0.08, "triangle"),
  pop: () => { tone(660, 0.07, "sine"); setTimeout(() => tone(880, 0.07, "sine"), 50); },
  place: () => { tone(400, 0.09, "square", 0.05); setTimeout(() => tone(600, 0.09, "square", 0.05), 60); },
  pickup: () => { tone(800, 0.07, "sine"); setTimeout(() => tone(500, 0.08, "sine"), 55); },
  chat: () => tone(700, 0.06, "triangle", 0.04),
  join: () => { tone(523, 0.1, "sine"); setTimeout(() => tone(784, 0.14, "sine"), 90); },
};
