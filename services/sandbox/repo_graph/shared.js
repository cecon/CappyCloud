'use strict'

const fs = require('fs')
const path = require('path')

const CODE_EXTENSIONS = new Set(['.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'])
const UI_DEFINITION_EXTENSIONS = new Set(['.glade'])
const REFERENCE_FILES = new Set([
  '.dockerignore',
  '.env.example',
  '.gitignore',
  '.npmignore',
  'app.json',
  'babel.config.js',
  'jest.config.js',
  'jsconfig.json',
  'metro.config.js',
  'package.json',
  'react-native.config.js',
  'tsconfig.json',
])
const SKIP_DIRS = new Set(['.git', '.idea', '.vscode', 'node_modules', 'dist', 'build', 'coverage', '.venv', 'venv', '__pycache__'])
const JS_IMPORT_RE =
  /\b(?:import|export)\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]|\brequire\(\s*['"]([^'"]+)['"]\s*\)|\bimport\(\s*['"]([^'"]+)['"]\s*\)/g
const PY_FROM_RE = /^\s*from\s+([.\w]+)\s+import\s+/gm
const PY_IMPORT_RE = /^\s*import\s+([.\w]+)/gm
const RESOLVE_EXTENSIONS = ['', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.py', '.glade']

function safeRepoPath(slug) {
  if (!/^[a-zA-Z0-9._-]+$/.test(slug || '')) throw new Error('slug inválido')
  const reposRoot = path.resolve('/repos')
  const repoPath = path.resolve(reposRoot, slug)
  const sessionsPath = path.resolve(reposRoot, 'sessions')
  if (!repoPath.startsWith(`${reposRoot}${path.sep}`) || repoPath === sessionsPath) {
    throw new Error('path de repo inválido')
  }
  if (!fs.existsSync(path.join(repoPath, '.git'))) {
    throw new Error('repositório não clonado no sandbox')
  }
  return repoPath
}

function isCodeFile(file) {
  const first = file.split('/')[0]
  return CODE_EXTENSIONS.has(path.posix.extname(file)) && !SKIP_DIRS.has(first)
}

function isReferenceFile(file) {
  const first = file.split('/')[0]
  const base = path.posix.basename(file)
  return !SKIP_DIRS.has(first) && REFERENCE_FILES.has(base)
}

function isUiDefinitionFile(file) {
  const first = file.split('/')[0]
  return UI_DEFINITION_EXTENSIONS.has(path.posix.extname(file)) && !SKIP_DIRS.has(first)
}

function moduleForFile(file) {
  const parts = file.split('/').filter(Boolean)
  if (parts.length === 0) return 'root'
  if (parts.length === 1) return 'root'
  if (parts[0] === 'services' && parts.length > 1) {
    if (parts[2] === 'app' && parts.length > 3) return `${parts[0]}/${parts[1]}/app/${parts[3]}`
    if (parts.length > 2) return `${parts[0]}/${parts[1]}/${parts[2]}`
    return `${parts[0]}/${parts[1]}`
  }
  if (parts[0] === 'web' && parts[1] === 'src' && parts.length > 2) return `web/src/${parts[2]}`
  if (parts[0] === 'docs' && parts.length > 1) return `docs/${parts[1]}`
  if (['apps', 'packages', 'libs', 'modules'].includes(parts[0]) && parts.length > 1) {
    return `${parts[0]}/${parts[1]}`
  }
  return parts[0]
}

function labelForFile(file) {
  return path.posix.basename(file)
}

module.exports = {
  CODE_EXTENSIONS,
  JS_IMPORT_RE,
  PY_FROM_RE,
  PY_IMPORT_RE,
  REFERENCE_FILES,
  RESOLVE_EXTENSIONS,
  SKIP_DIRS,
  UI_DEFINITION_EXTENSIONS,
  isCodeFile,
  isReferenceFile,
  isUiDefinitionFile,
  labelForFile,
  moduleForFile,
  safeRepoPath,
}
