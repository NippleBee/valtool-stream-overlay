import { test, expect, type BrowserContext } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { defaults } from '../../frontend/src/types'

let session: Awaited<ReturnType<BrowserContext['storageState']>>
let overlay: string

test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto(readFileSync('.cache/editor-32146.txt', 'utf8'))
  await expect(page.getByRole('heading', { name: 'Your overlay, your style.' })).toBeVisible()
  overlay = await page.getByLabel('OBS URL').inputValue()
  session = await context.storageState()
  await context.close()
})
test.beforeEach(async ({ page }) => {
  await page.context().addCookies(session.cookies)
  const response = await page.request.put('/api/settings', {
    headers: { Origin: 'http://127.0.0.1:32146' },
    data: defaults,
  })
  expect(response.ok()).toBeTruthy()
  await page.goto('/settings')
})

test('studio opens with local assets and a separate OBS URL', async ({ page }) => {
  const failures: string[] = []
  page.on('pageerror', (error) => failures.push(error.message))
  await expect(page.getByRole('heading', { name: 'Your overlay, your style.' })).toBeVisible()
  await expect(page.getByLabel('OBS URL')).toHaveValue(/\/overlay\/[a-f0-9]{48}$/)
  await expect(page.frameLocator('iframe').getByText('DIAMOND 2')).toBeVisible()
  await expect(page.frameLocator('iframe').locator('.rank-emblem img')).toHaveJSProperty(
    'complete',
    true,
  )
  await expect(page.locator('.brand-logo')).toHaveAttribute('src', '/logo.svg')
  await expect(page.locator('.brand-logo')).toHaveJSProperty('complete', true)
  await expect(page).toHaveTitle('ValTool Stream Overlay')
  expect(
    await page
      .frameLocator('iframe')
      .locator('.overlay-surface')
      .evaluate((el) => getComputedStyle(el, '::after').backgroundImage),
  ).toBe('none')
  expect(
    await page
      .locator('.preview-stage.checker')
      .evaluate((el) => getComputedStyle(el).backgroundImage),
  ).not.toBe('none')
  await expect(page.locator('.save-state')).toContainText('Saved')
  await page.screenshot({ path: 'artifacts/screenshots/studio-desktop.png', fullPage: true })
  expect(failures).toEqual([])
})

test('theme and title changes reach the same overlay renderer through SSE', async ({ page }) => {
  await page.getByRole('button', { name: 'Pastel' }).click()
  await page.getByLabel('Overlay title').fill('MY STREAM')
  await expect(page.locator('.save-state')).toContainText('Saved')
  await expect(page.frameLocator('iframe').locator('.overlay-card')).toHaveClass(/pastel/)
  await expect(page.frameLocator('iframe').getByText('MY STREAM')).toBeVisible()
  const source = await page.context().newPage()
  await source.goto(overlay)
  await expect(source.getByText('MY STREAM')).toBeVisible()
  await expect(source.locator('html')).toHaveClass(/overlay-document/)
  const background = await source
    .locator('body')
    .evaluate((el) => getComputedStyle(el).backgroundColor)
  expect(background).toBe('rgba(0, 0, 0, 0)')
  await source.screenshot({
    path: 'artifacts/screenshots/overlay-pastel.png',
    omitBackground: true,
  })
  await source.close()
})

test('aggregation window and recent strip stay independent', async ({ page }) => {
  await page.getByRole('tab', { name: 'Data', exact: true }).click()
  await page.getByRole('button', { name: '1', exact: true }).click()
  await expect(page.locator('.data-coverage')).toContainText('1 match included')
  const source = await page.context().newPage()
  await source.goto(overlay)
  await expect(source.locator('.overlay-stat').first()).toContainText('1.75')
  await expect(source.locator('.recent-agent')).toHaveCount(5)
  await source.close()
})

test('layout limits and metric selection persist after reload', async ({ page }) => {
  await page.getByRole('button', { name: 'Mini', exact: true }).click()
  await page.getByRole('tab', { name: 'Metrics', exact: true }).click()
  await expect(page.locator('.metric-option input:checked')).toHaveCount(1)
  await expect(
    page.locator('.metric-option').filter({ hasText: 'ACS' }).getByRole('checkbox'),
  ).toBeDisabled()
  await expect(page.locator('.save-state')).toContainText('Saved')
  await page.reload()
  await expect(page.getByRole('button', { name: 'Mini', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.locator('.obs-footer')).toContainText('220 × 70')
})

test('history and connection views are functional', async ({ page }) => {
  await page.getByRole('button', { name: 'Match history', exact: true }).click()
  await expect(page.locator('.match-table-row')).toHaveCount(100)
  await expect(page.locator('.match-table-row').first()).toContainText('Ascent')
  await page.getByRole('button', { name: 'Connection', exact: true }).click()
  await expect(page.locator('.connection-checks')).toContainText('Local server')
})

test('normal mode keeps demo previews out of its OBS output', async ({ browser }) => {
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto(readFileSync('.cache/editor-32147.txt', 'utf8'))
  await expect(page.getByRole('heading', { name: 'Your overlay, your style.' })).toBeVisible()
  await expect(page.frameLocator('iframe').getByText('DIAMOND 2')).toBeVisible()
  const url = await page.getByLabel('OBS URL').inputValue()
  const output = await context.newPage()
  await output.goto(url)
  await expect(output.getByText('NO DATA')).toBeVisible()
  await expect(output.getByText('DIAMOND 2')).toHaveCount(0)
  await page.getByRole('button', { name: 'Connection', exact: true }).click()
  await expect(page.locator('.connection-checks')).toContainText('Waiting')
  await context.close()
})

test('local API rejects foreign origins, missing editor sessions and invalid presets', async ({
  playwright,
  page,
}) => {
  const anonymous = await playwright.request.newContext()
  expect((await anonymous.get('http://127.0.0.1:32146/api/editor')).status()).toBe(401)
  expect((await anonymous.get(overlay.replace('/overlay/', '/api/overlay/'))).status()).toBe(200)
  expect(
    (
      await anonymous.put('http://127.0.0.1:32146/api/settings', {
        data: defaults,
        headers: { Origin: 'https://example.com' },
      })
    ).status(),
  ).toBe(403)
  expect(
    (
      await page.request.put('/api/settings', {
        data: { ...defaults, accent: 'url(https://example.com)' },
        headers: { Origin: 'http://127.0.0.1:32146' },
      })
    ).status(),
  ).toBe(400)
  const snapshot = await (await anonymous.get(overlay.replace('/overlay/', '/api/overlay/'))).json()
  expect(JSON.stringify(snapshot)).not.toMatch(/accessToken|entitlementsToken|password|overlayKey/)
  await anonymous.dispose()
})

test('small-screen editor remains usable without horizontal document overflow', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByLabel('OBS URL')).toBeVisible()
  const overflowing = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  expect(overflowing).toBeFalsy()
  await page.screenshot({ path: 'artifacts/screenshots/studio-mobile.png', fullPage: true })
})
