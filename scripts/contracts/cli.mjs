import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { generateAssets, checkAssets } from './assets.mjs';

const repoRoot = fileURLToPath(new URL('../../', import.meta.url));
const [command, flag, sourceCommit, ...extra] = process.argv.slice(2);

try {
  if (!['generate', 'check'].includes(command) || flag !== '--source-commit'
    || !sourceCommit || extra.length) {
    throw new Error('Usage: generate|check --source-commit <40-hex-commit>');
  }
  const options = { repoRoot, outputRoot: path.join(repoRoot, 'build/contracts'), sourceCommit };
  if (command === 'generate') {
    await generateAssets(options);
    console.log('Contract assets generated.');
  } else {
    const result = await checkAssets(options);
    if (!result.ok) {
      // Output paths can contain user-chosen filenames; do not log their contents.
      console.error('Contract assets differ; generate from the committed source.');
      process.exitCode = 1;
    } else console.log('Contract assets match.');
  }
} catch {
  console.error('Contract command failed. Use generate|check --source-commit <40-hex-commit> with valid committed source.');
  process.exitCode = 1;
}
