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
print(`${CYAN}${BOLD}Audison �?Instant Demo${RESET}`);
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

// ── Step 2: Check audison ────────────────────────────────
let installed = false;
try {
  execSync(`${pythonCmd} -c "import audison"`, { stdio: 'pipe' });
  installed = true;
} catch {
  installed = false;
}

// ── Step 3: Install if needed ──────────────────────────────────────
if (!installed) {
  print(`${YELLOW}Installing Audison...${RESET}`);
  print('');

  const pipCmd = getPipCommand();
  if (!pipCmd) {
    fail('pip is not available. Please install pip and try again.');
  }

  try {
    execSync(`${pipCmd} install --user audison`, { stdio: 'inherit' });
    print('');
    print(`${GREEN}Installation complete.${RESET}`);
  } catch (e) {
    fail('Failed to install audison.\n' +
         '  Try manually: pip install --user audison');
  }
} else {
  print(`${GREEN}Audison is already installed.${RESET}`);
}

print('');

// ── Step 4: Run audison example ────────────────────────────────────
try {
  execSync(`audison example`, { stdio: 'inherit' });
} catch {
  // If `audison` is not on PATH, try python -m
  try {
    execSync(`${pythonCmd} -m audison.cli example`, { stdio: 'inherit' });
  } catch {
    fail('Could not run audison example. Please try: pip install --user audison && audison example');
  }
}

// ── Step 5: Post-example guidance ──────────────────────────────────
print('');
print(`${BOLD}Want to audit your own code?${RESET}`);
print(`  ${CYAN}�?Open Playground: https://wdnmd1265.github.io/Audison/playground.html${RESET}`);
print(`  ${CYAN}�?Install CLI:     pip install --user audison && audison init${RESET}`);
print('');
