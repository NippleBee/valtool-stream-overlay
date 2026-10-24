import { spawn } from 'node:child_process'
import { backend, root } from './python.mjs'
const children = [
  backend(['-m', 'valtool_overlay', '--dev-ui', ...process.argv.slice(2)]),
  spawn(process.execPath, [root + '/node_modules/vite/bin/vite.js', '--host', '127.0.0.1'], {
    cwd: root + '/frontend',
    stdio: 'inherit',
  }),
]
let stopping = false
function stop(code = 0) {
  if (stopping) return
  stopping = true
  process.exitCode = code
  for (const child of children) if (child.exitCode === null) child.kill('SIGTERM')
}
for (const child of children) {
  child.on('exit', (code) => stop(code ?? 0))
  child.on('error', (error) => {
    console.error(error.message)
    stop(1)
  })
}
process.on('SIGINT', () => stop())
process.on('SIGTERM', () => stop())
