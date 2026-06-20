import { existsSync, readdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const MAC_CHROME_FOR_TESTING = 'Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'
const MAC_CHROME_HEADLESS_SHELL = 'chrome-headless-shell-mac-arm64/chrome-headless-shell'

function playwrightCacheRoots() {
  return [
    process.env.PLAYWRIGHT_BROWSERS_PATH && process.env.PLAYWRIGHT_BROWSERS_PATH !== '0'
      ? process.env.PLAYWRIGHT_BROWSERS_PATH
      : null,
    join(homedir(), 'Library/Caches/ms-playwright'),
    join(homedir(), '.cache/ms-playwright'),
  ].filter(Boolean)
}

function listPlaywrightCacheCandidates(prefix, pathsForEntry) {
  const candidates = []
  for (const root of playwrightCacheRoots()) {
    if (!existsSync(root)) continue

    let entries = []
    try {
      entries = readdirSync(root, { withFileTypes: true })
    } catch {
      continue
    }

    for (const entry of entries
      .filter((item) => item.isDirectory() && item.name.startsWith(prefix))
      .sort((a, b) => b.name.localeCompare(a.name))) {
      candidates.push(...pathsForEntry(root, entry.name))
    }
  }
  return candidates
}

function listPlaywrightHeadlessShellCandidates() {
  return listPlaywrightCacheCandidates('chromium_headless_shell-', (root, entryName) => [
    join(root, entryName, MAC_CHROME_HEADLESS_SHELL),
    join(root, entryName, 'chrome-headless-shell-mac-x64', 'chrome-headless-shell'),
    join(root, entryName, 'chrome-headless-shell-mac', 'chrome-headless-shell'),
    join(root, entryName, 'chrome-headless-shell-linux64', 'chrome-headless-shell'),
    join(root, entryName, 'chrome-headless-shell-linux', 'chrome-headless-shell'),
  ])
}

function listPlaywrightChromiumCandidates() {
  return listPlaywrightCacheCandidates('chromium-', (root, entryName) => [
    join(root, entryName, 'chrome-mac-arm64', MAC_CHROME_FOR_TESTING),
    join(root, entryName, 'chrome-mac', MAC_CHROME_FOR_TESTING),
    join(root, entryName, 'chrome-linux', 'chrome'),
  ])
}

export function findChrome(explicitPath) {
  const candidates = [
    explicitPath,
    process.env.CHROME_PATH,
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    ...listPlaywrightHeadlessShellCandidates(),
    ...listPlaywrightChromiumCandidates(),
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium',
  ].filter(Boolean)

  const match = candidates.find((candidate) => existsSync(candidate))
  if (!match) {
    throw new Error(
      'Chrome/Chromium executable not found. Pass --chrome, set CHROME_PATH, or install Playwright Chromium.',
    )
  }
  return match
}
