import {Config} from '@remotion/cli/config';
import fs from 'node:fs';

// PNG : donne un vrai yuv420p (le JPEG sort en yuvj420p, plage complète, moins compatible).
Config.setVideoImageFormat('png');
Config.setCodec('h264');
Config.setPixelFormat('yuv420p');
Config.setCrf(18);
Config.setOverwriteOutput(true);

// Utilise un Chromium déjà présent (utile hors-ligne / environnement restreint).
// Sinon Remotion télécharge lui-même son navigateur au premier rendu.
const localBrowser = [
  process.env.REMOTION_BROWSER_EXECUTABLE,
  '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell',
  '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
].find((p) => p && fs.existsSync(p));

if (localBrowser) {
  Config.setBrowserExecutable(localBrowser);
}
