// Rend plusieurs images clés d'un coup (un seul bundle) pour contrôler le visuel.
// Usage : node scripts/stills.mjs <dossier-sortie> <frame> [<frame> ...]
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [outDir, ...frames] = process.argv.slice(2);
if (!outDir || frames.length === 0) {
  console.error('Usage: node scripts/stills.mjs <dossier-sortie> <frame> [<frame> ...]');
  process.exit(1);
}
fs.mkdirSync(outDir, {recursive: true});

const browserExecutable = [
  process.env.REMOTION_BROWSER_EXECUTABLE,
  '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell',
  '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
].find((p) => p && fs.existsSync(p));

const serveUrl = await bundle({entryPoint: path.join(root, 'src/index.ts'), publicDir: path.join(root, 'public')});
const composition = await selectComposition({serveUrl, id: 'BackdropAd', browserExecutable});
console.log(`Composition : ${composition.width}x${composition.height} @${composition.fps}fps, ${composition.durationInFrames} images (${(composition.durationInFrames / composition.fps).toFixed(2)} s)`);

for (const f of frames) {
  const output = path.join(outDir, `frame-${String(f).padStart(4, '0')}.png`);
  await renderStill({composition, serveUrl, output, frame: Number(f), browserExecutable});
  console.log('→', output);
}
