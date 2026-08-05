import { mkdir, rm, stat } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.join(__dirname, '..')
const distDir = path.join(root, 'dist')
const outDir = path.join(root, 'public', 'downloads')
const outZip = path.join(outDir, 'material.zip')

function run(cmd, args, opts) {
  return new Promise((resolve, reject) => {
    const p = spawn(cmd, args, { stdio: 'inherit', shell: false, ...opts })
    p.on('error', (err) => {
      if (err.code === 'ENOENT') {
        reject(
          new Error(
            `No se encontró "${cmd}". En macOS/Linux suele venir instalado; en Windows instala zip o usa WSL.`,
          ),
        )
      } else {
        reject(err)
      }
    })
    p.on('close', (code) =>
      code === 0 ? resolve() : reject(new Error(`${cmd} salió con código ${code}`)),
    )
  })
}

async function main() {
  try {
    await stat(outZip)
    await rm(outZip)
    console.log(`Eliminado zip previo: ${path.relative(root, outZip)}`)
  } catch (e) {
    if (e?.code !== 'ENOENT') throw e
  }

  await run('npm', ['run', 'build'], { cwd: root })

  await mkdir(outDir, { recursive: true })

  // Contenido en la raíz del zip (equivalente a archiver.directory(dist, false))
  await run('zip', ['-qr', outZip, '.'], { cwd: distDir })

  console.log(`Listo: ${path.relative(root, outZip)}`)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
