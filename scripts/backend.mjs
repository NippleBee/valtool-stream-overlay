import { backend } from './python.mjs'
const args = process.argv.slice(2)
const child = backend(
  args[0] === '--pytest' ? ['-m', 'pytest', ...args.slice(1)] : ['-m', 'valtool_overlay', ...args],
)
process.on('SIGINT', () => child.kill('SIGINT'))
process.on('SIGTERM', () => child.kill('SIGTERM'))
child.on('exit', (code) => {
  process.exitCode = code ?? 0
})
