#!/usr/bin/env node
/**
 * Compare only a known rectangular UI or subtitle region using the bundled
 * Pixelmatch runner. This creates a temporary inverse mask and
 * never changes the source images.
 */
import {spawnSync} from 'node:child_process';
import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import {fileURLToPath} from 'node:url';

const EXIT = {PASS: 0, REGRESSION: 1, INPUT: 2};
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const defaultRunnerRoot = path.resolve(scriptDir, '../tools/visual-regression');

function usage(message) {
  if (message) console.error('Error: ' + message);
  console.error('Usage: node compare_roi.mjs --baseline <image> --actual <image> --diff <diff.png> --report <report.json> --roi <x,y,width,height> [options]\n\nOptions:\n  --threshold <0..1>                 Per-pixel threshold, passed to Pixelmatch.\n  --max-diff-pixels <count>          Allowed differing pixels in the ROI.\n  --max-diff-ratio <0..1>            Allowed differing-pixel ratio in the ROI.\n  --include-aa                       Count anti-aliased differences.\n  --visual-regression-root <path>    Existing visual-regression tool root when this Skill is copied elsewhere.\n  --help                             Show this help.');
  process.exit(EXIT.INPUT);
}

function readArgs(argv) {
  const values = {};
  const flags = new Set(['include-aa', 'help']);
  const allowed = new Set([
    'baseline', 'actual', 'diff', 'report', 'roi', 'threshold',
    'max-diff-pixels', 'max-diff-ratio', 'include-aa', 'visual-regression-root', 'help'
  ]);
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith('--')) usage('Unexpected argument: ' + token);
    const key = token.slice(2);
    if (!allowed.has(key)) usage('Unknown option: ' + token);
    if (flags.has(key)) {
      values[key] = true;
      continue;
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) usage('Missing value for --' + key);
    values[key] = value;
    index += 1;
  }
  if (values.help) usage();
  for (const required of ['baseline', 'actual', 'diff', 'report', 'roi']) {
    if (!values[required]) usage('Missing --' + required);
  }
  return values;
}

function parseRoi(value, image) {
  const fields = value.split(',').map(Number);
  if (fields.length !== 4 || fields.some((field) => !Number.isInteger(field))) {
    usage('--roi must be four integer values: x,y,width,height');
  }
  const [x, y, width, height] = fields;
  if (x < 0 || y < 0 || width < 1 || height < 1 || x + width > image.width || y + height > image.height) {
    usage('--roi must fit inside the baseline image (' + image.width + 'x' + image.height + ')');
  }
  return {x, y, width, height};
}

function readImage(filePath, tools) {
  const extension = path.extname(filePath).toLowerCase();
  const bytes = fs.readFileSync(filePath);
  if (extension === '.png') return tools.PNG.sync.read(bytes);
  if (extension === '.jpg' || extension === '.jpeg') {
    const decoded = tools.jpeg.decode(bytes, {useTArray: true, formatAsRGBA: true});
    if (decoded?.data) return decoded;
  }
  usage('Unable to decode baseline image: ' + filePath + '. Use PNG, JPG, or JPEG.');
}

function loadTools(root) {
  const packageJson = path.join(root, 'package.json');
  const runner = path.join(root, 'compare-images.mjs');
  if (!fs.existsSync(packageJson) || !fs.existsSync(runner)) {
    usage('Visual regression runner not found at ' + root + '. Install or point --visual-regression-root at a directory containing compare-images.mjs and package.json.');
  }
  const externalRequire = createRequire(packageJson);
  try {
    return {runner, PNG: externalRequire('pngjs').PNG, jpeg: externalRequire('jpeg-js')};
  } catch {
    usage('Visual regression dependencies are missing at ' + root + '. Run npm ci in that directory before using this wrapper.');
  }
}

function inverseRoiMask(roi, dimensions, PNG) {
  const mask = new PNG({width: dimensions.width, height: dimensions.height});
  mask.data.fill(255);
  for (let row = roi.y; row < roi.y + roi.height; row += 1) {
    for (let column = roi.x; column < roi.x + roi.width; column += 1) {
      const offset = (row * dimensions.width + column) * 4;
      mask.data[offset] = 0;
      mask.data[offset + 1] = 0;
      mask.data[offset + 2] = 0;
      mask.data[offset + 3] = 0;
    }
  }
  return mask;
}

function main() {
  const args = readArgs(process.argv.slice(2));
  const root = path.resolve(args['visual-regression-root'] || defaultRunnerRoot);
  const tools = loadTools(root);
  const baseline = readImage(args.baseline, tools);
  const roi = parseRoi(args.roi, baseline);
  const outputParent = path.dirname(path.resolve(args.report));
  fs.mkdirSync(outputParent, {recursive: true});
  const temp = fs.mkdtempSync(path.join(outputParent, 'pixelmatch-roi-'));
  const maskPath = path.join(temp, 'ignore-outside-roi.png');
  try {
    fs.writeFileSync(maskPath, tools.PNG.sync.write(inverseRoiMask(roi, baseline, tools.PNG)));
    const forwarded = [
      '--baseline', args.baseline, '--actual', args.actual, '--diff', args.diff, '--report', args.report,
      '--mask', maskPath
    ];
    for (const key of ['threshold', 'max-diff-pixels', 'max-diff-ratio']) {
      if (args[key] !== undefined) forwarded.push('--' + key, args[key]);
    }
    if (args['include-aa']) forwarded.push('--include-aa');
    const result = spawnSync(process.execPath, [tools.runner, ...forwarded], {encoding: 'utf8'});
    process.stdout.write(result.stdout || '');
    process.stderr.write(result.stderr || '');
    process.exitCode = result.status ?? EXIT.INPUT;
  } finally {
    fs.rmSync(temp, {recursive: true, force: true});
  }
}

main();
