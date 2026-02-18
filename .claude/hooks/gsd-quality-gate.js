#!/usr/bin/env node
// GSD Quality Gate Hook
// Runs Python syntax check on modified .py files before commit
// Integrates with GSD executor's verification chain

const { execSync } = require('child_process');
const fs = require('fs');

// Get staged Python files
let stagedFiles;
try {
  stagedFiles = execSync('git diff --cached --name-only --diff-filter=ACM', { encoding: 'utf8' })
    .trim()
    .split('\n')
    .filter(f => f.endsWith('.py'));
} catch (e) {
  process.exit(0); // Not in a git repo or no staged files
}

if (stagedFiles.length === 0) {
  process.exit(0);
}

let errors = 0;

for (const file of stagedFiles) {
  if (!fs.existsSync(file)) continue;

  try {
    execSync(`python -m py_compile "${file}"`, { encoding: 'utf8', stdio: 'pipe' });
  } catch (e) {
    console.error(`[GSD Quality Gate] Syntax error in ${file}`);
    console.error(e.stderr || e.message);
    errors++;
  }
}

if (errors > 0) {
  console.error(`\n[GSD Quality Gate] ${errors} file(s) failed syntax check. Fix before committing.`);
  process.exit(1);
}

process.exit(0);
