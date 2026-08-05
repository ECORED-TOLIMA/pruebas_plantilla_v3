/**
 * Reemplaza README.md por un título y la URL de GitHub Pages (base + nombre del repo).
 * Se invoca desde `npm run serve`.
 */
import { execSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const README_PATH = path.join(ROOT, 'README.md')

const GH_PAGES_BASE = 'https://ecoredsena-santander.github.io/'
const README_TITLE = '# URL WEB'

function repoSlugFromGitOrigin() {
  try {
    const url = execSync('git remote get-url origin', {
      cwd: ROOT,
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
    }).trim()
    const match = url.match(/(?:[/:])([^/]+?)(?:\.git)?$/i)
    return match ? match[1] : null
  } catch {
    return null
  }
}

function repoSlugFallback() {
  return path.basename(ROOT)
}

function buildReadme(slug) {
  const url = `${GH_PAGES_BASE}${slug}/`
  return `${README_TITLE}\n\n[${url}](${url})\n`
}

function syncReadme() {
  const slug = repoSlugFromGitOrigin() ?? repoSlugFallback()
  fs.writeFileSync(README_PATH, buildReadme(slug), 'utf8')
  console.info(
    `[sync-readme-github-pages-link] README actualizado → ${GH_PAGES_BASE}${slug}/`,
  )
}

syncReadme()
