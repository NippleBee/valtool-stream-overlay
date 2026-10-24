import { test, expect, type BrowserContext } from '@playwright/test'
import { mkdirSync, readFileSync } from 'node:fs'
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
  await expect(source.locator('.overlay-match-count')).toHaveText('1 MATCH')
  await source.close()
})

test('watermark toggles persist and every card shows the statistics match count without overlap', async ({
  page,
}) => {
  mkdirSync('work/watermark', { recursive: true })
  const source = await page.context().newPage()
  await source.goto(overlay)
  for (const theme of ['midnight', 'pastel'] as const) {
    for (const layout of ['large', 'compact', 'mini'] as const) {
      const metrics =
        layout === 'large'
          ? ['kd', 'winsLosses', 'winrate', 'acs', 'kda', 'rrNet']
          : layout === 'compact'
            ? ['kd', 'winsLosses', 'winrate']
            : ['kd']
      await page.request.put('/api/settings', {
        headers: { Origin: 'http://127.0.0.1:32146' },
        data: {
          ...defaults,
          theme,
          layout,
          metrics,
          matchCount: 1,
          recentCount: 5,
          showWatermark: true,
          ...(theme === 'pastel'
            ? { background: '#d6b4d0', accent: '#a779a1', textColor: '#664d68' }
            : {}),
        },
      })
      const card = source.locator(`.overlay-card.${layout}.${theme}`)
      await expect(card).toBeVisible()
      await expect(card.locator('.overlay-match-count')).toHaveText('1 MATCH')
      await expect(card.locator('.overlay-watermark')).toContainText('ValTool Stream Overlay')
      await expect(card.locator('.overlay-watermark img')).toHaveJSProperty('complete', true)
      expect(
        await card
          .locator('.overlay-watermark img')
          .evaluate((image) => (image as HTMLImageElement).naturalWidth),
      ).toBeGreaterThan(0)
      const bounds = await card.evaluate((element) => {
        const footer = element.querySelector<HTMLElement>('.overlay-footer')!
        const surface = element.querySelector<HTMLElement>('.overlay-surface')!
        const metrics = element.querySelector<HTMLElement>('.overlay-metrics')!
        return {
          footerTop: footer.getBoundingClientRect().top,
          footerBottom: footer.getBoundingClientRect().bottom,
          metricsBottom: metrics.getBoundingClientRect().bottom,
          surfaceBottom: surface.getBoundingClientRect().bottom,
          footerWidth: footer.clientWidth,
          footerContentWidth: footer.scrollWidth,
        }
      })
      expect(bounds.metricsBottom).toBeLessThanOrEqual(bounds.footerTop + 0.5)
      expect(bounds.footerBottom).toBeLessThanOrEqual(bounds.surfaceBottom)
      expect(bounds.footerContentWidth).toBeLessThanOrEqual(bounds.footerWidth)
      await source.screenshot({
        path: `work/watermark/${layout}-${theme}.png`,
        clip: (await card.boundingBox()) ?? undefined,
      })
    }
  }
  await page.reload()
  const toggle = page.getByRole('switch', { name: /^Show watermark/ })
  await expect(toggle).toBeChecked()
  await toggle.uncheck()
  await expect(source.locator('.overlay-watermark')).toHaveCount(0)
  await expect(source.locator('.overlay-match-count')).toHaveText('1 MATCH')
  await page.reload()
  await expect(page.getByRole('switch', { name: /^Show watermark/ })).not.toBeChecked()
  await page.getByRole('switch', { name: /^Show watermark/ }).check()
  await expect(source.locator('.overlay-watermark')).toBeVisible()
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
  await expect(page.locator('.obs-footer')).toContainText('440 × 140')
})

test('OBS render size uses a larger native canvas and fits legacy viewports without cropping', async ({
  page,
}) => {
  mkdirSync('work/readability', { recursive: true })
  const source = await page.context().newPage()
  await source.goto(overlay)
  await expect(
    page.getByRole('button', { name: 'OBS render size 200%', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(source.locator('.overlay-card')).toHaveCSS('transform', 'none')
  const actual = await source.locator('.overlay-card').boundingBox()
  expect(actual?.width).toBe(600)
  expect(actual?.height).toBe(356)
  const label = await source.locator('.overlay-stat > span').first().boundingBox()
  const value = await source.locator('.overlay-stat > strong').first().boundingBox()
  expect(label!.height).toBeGreaterThanOrEqual(16)
  expect(value!.height).toBeGreaterThanOrEqual(32)
  await source.screenshot({ path: 'work/readability/compact-2x.png', clip: actual! })
  await page.getByRole('button', { name: 'OBS render size 300%', exact: true }).click()
  await expect(page.locator('.obs-footer')).toContainText('900 × 534')
  await expect(source.locator('.overlay-card')).toHaveCSS('zoom', '3')
  await source.setViewportSize({ width: 300, height: 178 })
  await expect(source.locator('.overlay-card')).toHaveCSS('zoom', '1')
  expect((await source.locator('.overlay-card').boundingBox())?.width).toBe(300)
  await expect(source.locator('.overlay-match-count')).toBeVisible()
  await source.setViewportSize({ width: 1440, height: 1040 })
  await page.reload()
  await expect(
    page.getByRole('button', { name: 'OBS render size 300%', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await source.close()
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
  await expect(page.frameLocator('iframe').getByText('NO DATA')).toBeVisible()
  await page.getByRole('switch', { name: 'Show sample data in preview' }).check()
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

test('quit app explains OBS impact and shows a closed state without reconnecting', async ({
  page,
}) => {
  let shutdowns = 0
  await page.route('**/api/shutdown', async (route) => {
    shutdowns += 1
    await route.fulfill({ status: 202, body: '' })
  })
  page.once('dialog', async (dialog) => {
    expect(dialog.message()).toContain('OBS will stop receiving updates')
    await dialog.dismiss()
  })
  await page.getByRole('button', { name: 'Quit app', exact: true }).click()
  expect(shutdowns).toBe(0)
  await expect(page.getByRole('heading', { name: 'Your overlay, your style.' })).toBeVisible()
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Quit app', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'ValTool Stream Overlay is closed' }),
  ).toBeVisible()
  expect(shutdowns).toBe(1)
  await expect(page.getByText('Reconnecting automatically.')).toHaveCount(0)
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
