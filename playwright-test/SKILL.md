---
name: playwright-test
description: >
  Используй этот скилл когда пользователь говорит "напиши UI-тест", "создай playwright тест", "scaffold playwright", "протестируй фичу в браузере".
  Также используй после деплоя фичи 1С для создания автоматизированного регрессионного теста.
  Не используй для интерактивной автоматизации браузера — используй web-session или web-test.
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
---

# /playwright-test — Scaffold UI-теста для 1С фичи

Автономный Playwright-тест, который запускается без AI (`npm run test:ui`), пишет точечные наблюдения в JSONL, а агент выносит вердикт по логу.

## Когда использовать

- После деплоя фичи в базу (`/db-load-xml` → `/db-update`)
- Фича затрагивает UI (формы, кнопки, табличные части)

## Когда НЕ использовать

- Backend-only фича (новый MCP-инструмент, только BSL без форм)
- Изменения только в конфигурации/правах/подсистемах без UI-эффектов

---

## Шаг 1 — Scaffold инфраструктуры (одноразово на проект)

Проверить наличие `package.json` и `playwright.config.js` в корне целевого проекта.

Если отсутствуют — создать из шаблонов:

### package.json

```json
{
  "name": "<project-name>-tests",
  "private": true,
  "scripts": {
    "test:ui": "npx playwright test",
    "test:ui:headed": "npx playwright test --headed",
    "test:ui:debug": "npx playwright test --debug"
  },
  "devDependencies": {
    "@playwright/test": "^1.50.0"
  }
}
```

### playwright.config.js

```javascript
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/playwright',
  timeout: 60000,
  retries: 0,
  use: {
    // URL базы 1С — подставить из CLAUDE.md проекта
    baseURL: 'http://localhost:8080',
    // 1С веб-клиент: headless ненадёжен для некоторых действий
    headless: true,
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
  },
  projects: [
    {
      name: '1c-ui',
      use: { browserName: 'chromium' },
    },
  ],
});
```

После создания:
```bash
cd <project-root> && npm install && npx playwright install chromium
```

---

## Шаг 2 — Определить контрольные точки (UI checkpoints)

**До написания теста** — определить что именно проверяется. Источники:

1. **`openspec/changes/<feature>/design.md`** → секция `## UI checkpoints`
2. **Form.xml** фичи → элементы формы, кнопки, команды
3. **Здравый смысл** → после действия X что меняется на экране?

Формат контрольной точки:
```
<действие пользователя> → <ожидаемое наблюдение на экране>
```

Примеры:
```
Нажать "Провести" → заголовок содержит "№" и дату
Заполнить Контрагент → поле "Договор" стало доступно
Добавить строку в ТЧ Товары → количество строк увеличилось на 1
```

**Если после действия ничего не меняется визуально** — тест не может проверить. Нужно доработать UI (сообщение пользователю, смена статуса, индикатор).

---

## Шаг 3 — Сгенерировать spec.js

Создать `tests/playwright/<feature>.spec.js` по паттерну:

```javascript
// tests/playwright/<feature>.spec.js
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const LOG_FILE = path.join(__dirname, '<feature>.log.jsonl');
const BASE_URL = '<base-url-from-project-docs>';

// --- Logging helpers ---
function log(step, observation) {
  const entry = {
    ts: new Date().toISOString(),
    step,
    ...observation,
  };
  fs.appendFileSync(LOG_FILE, JSON.stringify(entry) + '\n');
}

function clearLog() {
  if (fs.existsSync(LOG_FILE)) fs.unlinkSync(LOG_FILE);
}

// --- 1C helpers ---
async function clipboardPaste(page, value) {
  await page.evaluate((v) => navigator.clipboard.writeText(v), value);
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Control+V');
}

async function checkFormClosed(page) {
  const hasModal = await page.locator('.modalSurface').count() > 0;
  const hasValidation = await page.locator('[title="Закрыть (Ctrl+Shift+Z)"]')
    .filter({ visible: true }).count() > 0;
  return { hasModal, hasValidation };
}

// --- Tests ---
test.describe('<Feature Name>', () => {
  test.beforeAll(() => clearLog());

  test('checkpoint: <description>', async ({ page }) => {
    // Navigate
    await page.goto(BASE_URL);
    await page.waitForTimeout(2000); // 1C web client init

    // Action
    // ... (clipboard paste, DLB clicks, etc.)

    // Observe — точечная проверка, НЕ полный DOM
    const fieldValue = await page.locator('[id$="_FieldName"]').textContent();
    const isVisible = await page.locator('[id$="_Element"]').isVisible();

    log('checkpoint-name', {
      fieldValue,
      isVisible,
      pass: fieldValue === 'expected',
    });

    expect(fieldValue).toBe('expected');
  });
});
```

### Правила генерации spec.js

1. **Один test() на контрольную точку** — изолированная проверка
2. **JSONL-лог обязателен** — каждый `test()` пишет `log(step, observation)`
3. **Наблюдения точечные**: `isVisible`, `textContent`, `count` — НЕ полный снапшот
4. **Селекторы 1С**: суффиксные `[id$="_FieldName_DLB"]`, НИКОГДА хардкод формы `form40_`
5. **Ввод только через clipboard** — стандартные `fill()`/`type()` не работают в 1С
6. **aria-label и текст кнопок** — не CSS-классы (нестабильны в 1С)

### Анализ Form.xml для генерации

Прочитать Form.xml фичи (через Read или `/form-info`), извлечь:
- Имена элементов → суффиксные селекторы `[id$="_<ElementName>"]`
- Команды → кнопки для нажатия
- Реквизиты формы → поля для проверки значений
- TabularSection → проверка количества строк

---

## Шаг 4 — Запустить тест

```bash
cd <project-root> && npm run test:ui 2>&1 || true
```

Если есть ошибки Playwright setup (браузер не установлен):
```bash
npx playwright install chromium
```

---

## Шаг 5 — Вердикт

AI читает два источника и выносит оценку:

### 1. JSONL-лог теста

```bash
cat tests/playwright/<feature>.log.jsonl
```

Каждая строка — JSON-объект с `step`, `pass`, и observation-полями. Проверить: все `pass: true`?

### 2. Журнал регистрации 1С

```json
{"name": "get_event_log", "arguments": {"count": 20}}
```

Проверить: нет ли ошибок, связанных с фичей, после прогона теста?

### Формат вердикта

```
UI-тест: ✅ PASS (N/N checkpoints)
  - checkpoint-1: OK (field = "expected")
  - checkpoint-2: OK (element visible)
Журнал 1С: нет ошибок
```

или

```
UI-тест: ❌ FAIL (N-1/N checkpoints)
  - checkpoint-1: OK
  - checkpoint-2: FAIL (expected "Проведён", got "Новый")
  → Воспроизвести через Playwright MCP, browser_snapshot на шаге 2
```

### При FAIL

Не повторять тест автоматически. Воспроизвести проблемный шаг через Playwright MCP (`browser_navigate` → `browser_snapshot`) для диагностики. `browser_snapshot` — инструмент отладки, не основной механизм.

---

## Полный пример (end-to-end)

```
1. /db-load-xml + /db-update (фича уже в базе)
2. Проверить tests/ инфраструктуру → scaffold если нет
3. Прочитать Form.xml → извлечь элементы
4. Определить checkpoints из design.md
5. Сгенерировать tests/playwright/payment-form.spec.js
6. npm run test:ui → читать .log.jsonl
7. get_event_log → проверить ошибки
8. Вердикт: PASS/FAIL + детали
```

---

## Ограничения

- Только Chromium (1С веб-клиент оптимизирован под него)
- `headless: true` может не работать для некоторых 1С-действий — переключить на `headed` через `test:ui:headed`
- Тест проверяет UI-поведение, не бизнес-логику. Для бизнес-логики используй локальный тестовый workflow проекта, если он настроен.
- package.json и playwright.config.js живут в целевом проекте, не в этом workspace
- Clipboard paste требует разрешений — Chromium grant по умолчанию

## Связанные скилы

- `/web-session` — интерактивная работа с 1С в браузере (для отладки теста)
- локальный unit-test workflow проекта — unit-тестирование бизнес-логики (серверная сторона)
- `/form-info` — анализ Form.xml для извлечения элементов
- `/db-load-xml` + `/db-update` — деплой фичи перед тестом
