import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawn } from 'node:child_process'
export const root = resolve(import.meta.dirname, '..')
const venv = resolve(
  root,
  'backend/.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
)
export const python =
  process.env.VALTOOL_PYTHON ||
  (existsSync(venv) ? venv : process.platform === 'win32' ? 'python' : 'python3')
export function backend(args = [], options = {}) {
  const child = spawn(python, args, { cwd: resolve(root, 'backend'), stdio: 'inherit', ...options })
  child.on('error', (error) => {
    console.error(error.message)
    process.exitCode = 1
  })
  return child
}
