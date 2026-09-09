import test from 'node:test';
import assert from 'node:assert/strict';
import { money, fmtVal, fmtTokens, paretoFrontier, ticks } from '../site/lib.js';

const pt = (name, cost, cap) => ({ name, cost, cap });
const C = m => m.cost, P = m => m.cap;

test('the frontier keeps only models nothing else beats on both axes', () => {
  const rows = [
    pt('cheap-weak', 1, 10),
    pt('cheap-strong', 2, 40),
    pt('dear-weak', 8, 30),      // dominated: cheap-strong is cheaper and better
    pt('dear-strong', 10, 50),
  ];
  assert.deepEqual(paretoFrontier(rows, C, P).map(m => m.name),
    ['cheap-weak', 'cheap-strong', 'dear-strong']);
});

test('the frontier rises monotonically in capability', () => {
  const rows = Array.from({ length: 60 }, (_, i) =>
    pt('m' + i, (i * 7 % 23) + 1, (i * 13 % 41)));
  const f = paretoFrontier(rows, C, P);
  for (let i = 1; i < f.length; i++) {
    assert.ok(C(f[i]) >= C(f[i - 1]), 'cost never decreases along the frontier');
    assert.ok(P(f[i]) > P(f[i - 1]), 'capability strictly increases along the frontier');
  }
});

test('no model beats a frontier model on both axes at once', () => {
  const rows = Array.from({ length: 40 }, (_, i) =>
    pt('m' + i, ((i * 31) % 97) / 3 + 0.5, (i * 17) % 53));
  const f = paretoFrontier(rows, C, P);
  for (const k of f) {
    assert.ok(!rows.some(o => o !== k && C(o) <= C(k) && P(o) > P(k)),
      `${k.name} should not be dominated`);
  }
});

test('on a cost tie only the stronger model survives', () => {
  const rows = [pt('weak', 5, 10), pt('strong', 5, 30)];
  assert.deepEqual(paretoFrontier(rows, C, P).map(m => m.name), ['strong']);
});

test('an empty set has an empty frontier', () => {
  assert.deepEqual(paretoFrontier([], C, P), []);
});

test('log ticks land on 1, 2 and 5 within the range', () => {
  assert.deepEqual(ticks(0.9, 12, true), [1, 2, 5, 10]);
});

test('a wide log range falls back to decades only', () => {
  const t = ticks(0.001, 1000, true);
  assert.ok(t.every(v => Math.abs(Math.log10(v) % 1) < 1e-9), 'decades only');
  assert.ok(t.length <= 9);
});

test('linear ticks stay inside the range and stay round', () => {
  const t = ticks(0, 50, false);
  assert.ok(t.length >= 3 && t.length <= 8);
  assert.equal(t[0], 0);
  assert.ok(t[t.length - 1] <= 50);
});

test('money shortens as the magnitude grows', () => {
  assert.equal(money(1234), '$1234');
  assert.equal(money(7.6297), '$7.63');
  assert.equal(money(0.42), '$0.420');
  assert.equal(money(0.0031), '$0.0031');
});

test('index scores and benchmark fractions read differently', () => {
  assert.equal(fmtVal(53.37, 'index'), '53.4');
  assert.equal(fmtVal(0.8123, 'frac'), '81.2%');
});

test('token counts get a magnitude suffix', () => {
  assert.equal(fmtTokens(1.87e12), '1.9T');
  assert.equal(fmtTokens(3.4e9), '3.4B');
});
