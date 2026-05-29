#!/usr/bin/env node
const { execSync } = require('child_process');

const RESET = '\x1b[0m';
const CYAN = '\x1b[36m';
const YELLOW = '\x1b[33m';
const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const BOLD = '\x1b[1m';

function print(msg) {
  console.log(msg);
}

function fail(msg) {
  console.error(`${RED}${BOLD}[ERROR]${RESET} ${msg}`);
  process.exit(1);
}

function checkCommand(cmd) {
  try {
    execSync(`${cmd} --version`, { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

function getPipCommand() {
  if (checkCommand('pip3')) return 'pip3';
  if (checkCommand('pip')) return 'pip';
  return null;
}

// ── Step 1: Check Python ──────────────────────────────────────────
print('');
print(`${CYAN}${BOLD}AI Flow Architect — Instant Demo${RESET}`);
print('');

if (!checkCommand('python3') && !checkCommand('python')) {
  fail('Python 3.10+ is required but was not found on your PATH.\n' +
       '  Please install Python from https://python.org and ensure it is added to PATH.');
}

const pythonCmd = checkCommand('python3') ? 'python3' : 'python';

try {
  const pyVersion = execSync(`${pythonCmd} -c "import sys; print(sys.version_info.major, sys.version_info.minor)"`, {
    encoding: 'utf-8',
    stdio: 'pipe'
  }).trim();
  const [major, minor] = pyVersion.split(' ').map(Number);
  if (major < 3 || (major === 3 && minor < 10)) {
    fail(`Python 3.10+ is required. Detected: ${major}.${minor}`);
  }
} catch {
  fail('Could not determine Python version. Please ensure Python 3.10+ is installed.');
}

// ── Step 2: Check ai-flow-architect ────────────────────────────────
let installed = false;
try {
  execSync(`${pythonCmd} -c "import ai_flow_architect"`, { stdio: 'pipe' });
  installed = true;
} catch {
  installed = false;
}

// ── Step 3: Install if needed ──────────────────────────────────────
if (!installed) {
  print(`${YELLOW}Installing AI Flow Architect...${RESET}`);
  print('');

  const pipCmd = getPipCommand();
  if (!pipCmd) {
    fail('pip is not available. Please install pip and try again.');
  }

  try {
    execSync(`${pipCmd} install --user ai-flow-architect`, { stdio: 'inherit' });
    print('');
    print(`${GREEN}Installation complete.${RESET}`);
  } catch (e) {
    fail('Failed to install ai-flow-architect.\n' +
         '  Try manually: pip install --user ai-flow-architect');
  }
} else {
  print(`${GREEN}AI Flow Architect is already installed.${RESET}`);
}

print('');

// ── Step 4: Run ai-flow example ────────────────────────────────────
try {
  execSync(`ai-flow example`, { stdio: 'inherit' });
} catch {
  // If `ai-flow` is not on PATH, try python -m
  try {
    execSync(`${pythonCmd} -m ai_flow_architect.cli example`, { stdio: 'inherit' });
  } catch {
    fail('Could not run ai-flow example. Please try: pip install --user ai-flow-architect && ai-flow example');
  }
}

// ── Step 5: Post-example guidance ──────────────────────────────────
print('');
print(`${BOLD}Want to audit your own code?${RESET}`);
print(`  ${CYAN}→ Open Playground: https://wdnmd1265.github.io/ai-flow-architect/playground.html${RESET}`);
print(`  ${CYAN}→ Install CLI:     pip install --user ai-flow-architect && ai-flow init${RESET}`);
print('');
