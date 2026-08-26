/**
 * 1C Screenshot Utility
 *
 * Сохраняет скриншоты в playwright-screenshots/, автоочищает старые файлы.
 * Читает/пишет кеш селекторов в .claude/1c-web-cache.json (per-project).
 *
 * Использование — скриншот текущей страницы:
 *   browser_run_code(code=`
 *     ${read('<skills-root>/web-session/scripts/1c-screenshot.js')}
 *     return await screenshot1C(page, 'form-name');
 *   `)
 *
 * Использование — прочитать кешированный селектор:
 *   const cache = loadCache('http://127.0.0.1/demo');
 *   // cache.login.userInput, cache.selectors['МойКлюч']
 *
 * Использование — сохранить найденный селектор:
 *   saveSelector('http://127.0.0.1/demo', 'login.userInput', 'input[name="user"]');
 */

const fs = require('fs');
const path = require('path');

// Пути относительно CWD (корень проекта)
const SCREENSHOTS_DIR = path.join(process.cwd(), 'playwright-screenshots');
const CACHE_FILE = path.join(process.cwd(), '.claude', '1c-web-cache.json');

// ── Screenshot ────────────────────────────────────────────────────────────────

/**
 * Сделать скриншот и сохранить в playwright-screenshots/<name>-<timestamp>.png
 * Автоматически удаляет файлы старше maxAgeDays (по умолчанию 7).
 *
 * @param {import('playwright').Page} page
 * @param {string} name  — префикс имени файла (например 'form-nomenclature')
 * @param {object} opts  — { fullPage: false, maxAgeDays: 7 }
 * @returns {{ file, filename, cleaned }}
 */
async function screenshot1C(page, name = 'screenshot', opts = {}) {
  const { fullPage = false, maxAgeDays = 7 } = opts;

  if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  }

  // Автоочистка
  const cleaned = _cleanOldScreenshots(maxAgeDays);

  // Имя файла: name-2026-02-27T10-30-00.png
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const safeName = name.replace(/[^a-zа-яёА-ЯЁ0-9_-]/gi, '-');
  const filename = `${safeName}-${ts}.png`;
  const file = path.join(SCREENSHOTS_DIR, filename);

  await page.screenshot({ path: file, fullPage });

  return { file, filename, cleaned };
}

/**
 * Удалить файлы старше N дней из playwright-screenshots/
 * @returns {number} количество удалённых файлов
 */
function _cleanOldScreenshots(daysOld) {
  if (!fs.existsSync(SCREENSHOTS_DIR)) return 0;
  const cutoff = Date.now() - daysOld * 24 * 60 * 60 * 1000;
  let removed = 0;
  fs.readdirSync(SCREENSHOTS_DIR).forEach(file => {
    if (!/\.(png|jpg|jpeg)$/i.test(file)) return;
    const fp = path.join(SCREENSHOTS_DIR, file);
    if (fs.statSync(fp).mtimeMs < cutoff) {
      fs.unlinkSync(fp);
      removed++;
    }
  });
  return removed;
}

// ── Selector Cache ────────────────────────────────────────────────────────────

/**
 * Загрузить кеш селекторов для базы.
 * @param {string} baseUrl  — например 'http://127.0.0.1/demo'
 * @returns {object} кеш для этой базы (или пустой объект)
 */
function loadCache(baseUrl) {
  if (!fs.existsSync(CACHE_FILE)) return {};
  const all = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
  return all[baseUrl] ?? {};
}

/**
 * Сохранить найденный селектор в кеш.
 * Ключ поддерживает точечную нотацию: 'login.userInput', 'selectors.btnPost'
 *
 * @param {string} baseUrl  — 'http://127.0.0.1/demo'
 * @param {string} key      — 'login.userInput' или 'selectors.МойКлюч'
 * @param {string} value    — CSS-селектор или Playwright locator string
 */
function saveSelector(baseUrl, key, value) {
  const all = fs.existsSync(CACHE_FILE)
    ? JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'))
    : {};

  if (!all[baseUrl]) all[baseUrl] = { selectors: {} };

  // Точечная нотация: 'login.userInput' → all[baseUrl].login.userInput
  const parts = key.split('.');
  let target = all[baseUrl];
  for (let i = 0; i < parts.length - 1; i++) {
    if (!target[parts[i]]) target[parts[i]] = {};
    target = target[parts[i]];
  }
  target[parts[parts.length - 1]] = value;

  fs.writeFileSync(CACHE_FILE, JSON.stringify(all, null, 2), 'utf8');
  return { saved: true, key, value };
}

/**
 * Попробовать кешированный селектор, при неудаче — использовать fallback.
 *
 * @param {import('playwright').Page} page
 * @param {string} baseUrl
 * @param {string} cacheKey   — 'login.userInput'
 * @param {string[]} fallbacks — массив CSS-селекторов для перебора
 * @returns {import('playwright').Locator | null}
 */
async function locatorWithCache(page, baseUrl, cacheKey, fallbacks = []) {
  const cache = loadCache(baseUrl);
  const parts = cacheKey.split('.');
  let cached = cache;
  for (const p of parts) cached = cached?.[p];

  if (cached) {
    const loc = page.locator(cached).first();
    if (await loc.isVisible({ timeout: 1500 }).catch(() => false)) {
      return loc; // Кеш работает
    }
  }

  // Перебираем fallback-селекторы
  for (const sel of fallbacks) {
    const loc = page.locator(sel).first();
    if (await loc.isVisible({ timeout: 1500 }).catch(() => false)) {
      saveSelector(baseUrl, cacheKey, sel); // Сохраняем найденный
      return loc;
    }
  }

  return null;
}
