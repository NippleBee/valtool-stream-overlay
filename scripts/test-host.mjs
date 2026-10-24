import { mkdirSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve, join } from 'node:path'
import { backend } from './python.mjs'
const index = process.argv.indexOf('--port')
const port =
  index >= 0 ? Number(process.argv[index + 1]) : process.argv.includes('--live') ? 32147 : 32146
mkdirSync('.cache', { recursive: true })
const data = mkdtempSync(join(tmpdir(), `valtool-e2e-${port}-`))
const child = backend([
  '-m',
  'valtool_overlay',
  '--no-browser',
  '--port',
  String(port),
  '--data-dir',
  data,
  '--editor-url-file',
  resolve(`.cache/editor-${port}.txt`),
  ...(!process.argv.includes('--live') ? ['--demo'] : []),
])
process.on('SIGINT', () => child.kill('SIGINT'))
process.on('SIGTERM', () => child.kill('SIGTERM'))
child.on('exit', (code) => {
  rmSync(data, { recursive: true, force: true })
  process.exitCode = code ?? 0
})
