import { spawn } from 'node:child_process'
import { backend, root } from './python.mjs'
const pythonTests = backend(['-m', 'pytest'])
pythonTests.on('exit', (code) => {
  if (code !== 0) {
    process.exitCode = code ?? 1
    return
  }
  const frontendTests = spawn(process.execPath, [root + '/node_modules/vitest/vitest.mjs', 'run'], {
    cwd: root + '/frontend',
    stdio: 'inherit',
  })
  frontendTests.on('exit', (result) => {
    process.exitCode = result ?? 1
  })
})
