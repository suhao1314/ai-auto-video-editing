import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const scripts = path.dirname(fileURLToPath(import.meta.url));
const runnerRoot = path.resolve(scripts, '../tools/visual-regression');
const {PNG} = createRequire(path.join(runnerRoot, 'package.json'))('pngjs');
const cli = path.join(scripts, 'compare_roi.mjs');

function makeImage(filePath, changedAt) {
  const image = new PNG({width: 20, height: 20});
  image.data.fill(255);
  if (changedAt) {
    const [x, y] = changedAt;
    const offset = (y * image.width + x) * 4;
    image.data[offset] = 0;
    image.data[offset + 1] = 100;
    image.data[offset + 2] = 220;
  }
  fs.writeFileSync(filePath, PNG.sync.write(image));
}

function execute(directory, actual, roi) {
  return spawnSync(process.execPath, [
    cli, '--baseline', path.join(directory, 'baseline.png'), '--actual', actual,
    '--diff', path.join(directory, 'diff-' + roi.replaceAll(',', '-') + '.png'),
    '--report', path.join(directory, 'report-' + roi.replaceAll(',', '-') + '.json'),
    '--roi', roi, '--visual-regression-root', runnerRoot
  ], {encoding: 'utf8'});
}

test('changes inside the ROI are reported', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'compare-roi-'));
  try {
    makeImage(path.join(directory, 'baseline.png'));
    const actual = path.join(directory, 'inside.png');
    makeImage(actual, [8, 8]);
    const result = execute(directory, actual, '5,5,10,10');
    assert.equal(result.status, 1, result.stderr);
    const report = JSON.parse(fs.readFileSync(path.join(directory, 'report-5-5-10-10.json')));
    assert.ok(report.diffPixels > 0);
    assert.equal(report.comparedPixels, 100);
  } finally {
    fs.rmSync(directory, {recursive: true, force: true});
  }
});

test('changes outside the ROI are ignored', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'compare-roi-'));
  try {
    makeImage(path.join(directory, 'baseline.png'));
    const actual = path.join(directory, 'outside.png');
    makeImage(actual, [2, 2]);
    const result = execute(directory, actual, '5,5,10,10');
    assert.equal(result.status, 0, result.stderr);
    const report = JSON.parse(fs.readFileSync(path.join(directory, 'report-5-5-10-10.json')));
    assert.equal(report.diffPixels, 0);
    assert.equal(report.comparedPixels, 100);
  } finally {
    fs.rmSync(directory, {recursive: true, force: true});
  }
});

test('an out-of-range ROI is rejected before a diff is written', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'compare-roi-'));
  try {
    makeImage(path.join(directory, 'baseline.png'));
    const actual = path.join(directory, 'invalid.png');
    makeImage(actual);
    const result = execute(directory, actual, '18,18,3,3');
    assert.equal(result.status, 2);
    assert.equal(fs.existsSync(path.join(directory, 'diff-18-18-3-3.png')), false);
  } finally {
    fs.rmSync(directory, {recursive: true, force: true});
  }
});
