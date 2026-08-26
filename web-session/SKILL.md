---
name: web-session
description: >
  Используй этот скилл для управления 1С:Предприятие в веб-клиенте через Playwright MCP: запуск/перезапуск/завершение сеанса, навигация, создание и редактирование справочников и документов.
  Также используй для генерации тестовых данных через UI и сценарного тестирования в браузере.
  Не используй для scaffold автотестов — используй playwright-test.
allowed-tools:
  - Read
  - Write
  - Glob
  - Bash
  - mcp__playwright__browser_navigate
  - mcp__playwright__browser_snapshot
  - mcp__playwright__browser_click
  - mcp__playwright__browser_type
  - mcp__playwright__browser_press_key
  - mcp__playwright__browser_run_code
  - mcp__playwright__browser_handle_dialog
  - mcp__playwright__browser_take_screenshot
  - mcp__playwright__browser_evaluate
  - mcp__playwright__browser_console_messages
  - mcp__playwright__browser_wait_for
  - mcp__playwright__browser_tabs
---

# /web-session — Управление 1С в веб-клиенте

Скилл для работы с 1С:Предприятие через Playwright MCP (браузер).

> **Источник:** адаптировано из [RooLee10/web-session](https://github.com/RooLee10/web-session) (MIT)

## Запуск базы

1. Прочитать `CLAUDE.md` проекта — найти URL базы (формат: `http://<сервер>/<публикация>/ru_RU/`)
2. `browser_navigate` на URL
3. Обработать лицензию/вход если появятся (см. ниже)

## Завершение и перезапуск

**Сервис и настройки** → **Файл** → **Выход** → **Завершить работу**

Перезапуск: завершить → `browser_navigate` на URL.

---

## КРИТИЧЕСКИЕ ПРАВИЛА 1С веб-клиента

### 1. Clipboard paste — ЕДИНСТВЕННЫЙ способ ввода

**Стандартные `fill()`, `type()`, `pressSequentially()` НЕ работают в 1С.** Всегда:

```javascript
await page.evaluate((v) => navigator.clipboard.writeText(v), 'Значение');
await page.keyboard.press('Control+A');  // очистить поле
await page.keyboard.press('Control+V');
```

### 2. Суффиксные селекторы — ЕДИНСТВЕННЫЙ надёжный метод

Формы 1С получают инкрементальные ID (`form26`, `form40`). **Никогда не хардкодить номер формы.**

```javascript
// ПРАВИЛЬНО
await page.locator('[id$="_ВидНоменклатуры_DLB"]').click();
// НЕПРАВИЛЬНО — сломается после первой формы
await page.locator('[id="form40_ВидНоменклатуры_DLB"]').click();
```

### 3. DLB-кнопки — универсальный паттерн выбора

**Все кнопки выбора имеют суффикс `_DLB`** — и перечисления, и справочники:

```javascript
await page.locator('[id$="_ВидАттракциона_DLB"]').click();
await page.waitForTimeout(100);

if (await page.locator('#editDropDown').count() > 0) {
  // Dropdown — перечисление или небольшой справочник
  await page.locator('#editDropDown').getByText('Экстремальный').click();
} else {
  // Picker — большой справочник
  await page.getByTitle('Выбрать значение (Ctrl+Enter)').waitFor();
  await page.getByText('Экстремальный').click();
  await page.getByTitle('Выбрать значение (Ctrl+Enter)').click();
}
```

### 4. Навигационный кеш

ID разделов (`#themesCell_theme_N`) и пунктов меню (`#cmd_0_3_txt`) уникальны для каждой базы.

При первом запуске — выполнить `references/scan-nav.js` через `browser_run_code`, результат сохранить в `.codex/1c-nav.json` (Write tool).

Навигация — только через кешированные ID:
```javascript
await page.locator('#themesCell_theme_1').click();  // из 1c-nav.json
await page.locator('#cmd_0_3_txt').waitFor({ state: 'visible', timeout: 2000 });
await page.locator('#cmd_0_3_txt').click();
```

**НЕ** использовать `getByText('Справочники')` — `strict mode violation`.

---

## Обработка диалогов

### Диалог лицензии

"Не обнаружено свободной лицензии!" — установить checkbox через JS, нажать "Выполнить запуск":

```javascript
async (page) => {
  const rows = await page.locator('text=сеанс:').all();
  for (const row of rows) {
    const parent = row.locator('xpath=..');
    await parent.locator('input, [class*="check"], [class*="box"]').first().click();
  }
  return { clicked: rows.length };
}
```

### Форма входа

Если появляется — сразу `browser_navigate` с тем же URL. **Не нажимать "Войти".**

### Модальные диалоги

| Диалог | Действие |
|--------|----------|
| `beforeunload` | `browser_handle_dialog` с `accept: true` |
| "Данные были изменены" | `locator('a').filter({ hasText: 'Нет' }).click()` |
| Подтверждение (Пометить на удаление?) | `page.keyboard.press('Enter')` |

---

## Клавиатурные сочетания

| Сочетание | Действие |
|-----------|----------|
| `Ctrl+Enter` | Записать и закрыть / Провести и закрыть |
| `Ctrl+S` | Записать (без проведения) |
| `Escape` | Закрыть диалог ошибки |
| `Tab` | Следующее поле |
| `F4` | Показать список для выбора |
| `Ins` | Добавить строку в табличную часть |
| `Ctrl+Shift+Z` | Закрыть панель ошибок валидации |
| `Delete` | Пометить на удаление |

**Проведение:** `Ctrl+Enter` проводит и формирует движения. `Ctrl+S` только записывает.

---

## Поле "Наименование" при создании

Поле "Наименование" уже в фокусе при открытии формы нового элемента. Не искать по ID:

```javascript
await page.keyboard.press('Control+A');
await page.evaluate((v) => navigator.clipboard.writeText(v), name);
await page.keyboard.press('Control+V');
```

---

## Табличные части

Добавить строку (`Ins`), заполнить clipboard paste + `Tab` между полями.

**Справочник в ячейке:**
```javascript
await page.keyboard.press('F4');
await page.waitForTimeout(300);
await page.getByTitle('Выбрать значение (Ctrl+Enter)').waitFor();
const pickerSearch = page.getByRole('textbox', { name: 'Поиск (Ctrl+F)' }).last();
await pickerSearch.click();
await page.evaluate((v) => navigator.clipboard.writeText(v), 'Текст поиска');
await page.keyboard.press('Control+V');
await page.waitForTimeout(600);
await page.locator('.gridBoxText').filter({ hasText: /Текст поиска/ }).first().click({ force: true });
await page.getByTitle('Выбрать значение (Ctrl+Enter)').click();
```

**При нескольких таблицах на форме** — скоупить к нужной командной панели:
```javascript
await page.locator('[id$="_ТоварыКоманднаяПанель"]').last()
  .getByTitle('Добавить новый элемент (Ins)').click();
```

---

## Создание объекта из dropdown

Если нужного элемента нет в справочнике:
```javascript
await page.locator('[id$="_Филиал_DLB"]').click();
await page.waitForTimeout(200);
await page.getByTitle('Создать (F8)').click();
await page.waitForTimeout(500);
// Форма нового объекта — после Ctrl+Enter подставится автоматически
```

---

## Группы в иерархических справочниках

Развернуть/свернуть — двойной клик. При создании внутри развёрнутой группы поле "Группа" заполняется автоматически.

---

## JS-верификация (вместо screenshot)

После `Ctrl+Enter` проверить результат прямо в `browser_run_code`:

```javascript
await page.waitForTimeout(800);
const hasModal = await page.locator('.modalSurface').count() > 0;
const formOpen = await page.getByRole('textbox', { name: 'Наименование:' }).count() > 0;
const hasValidationPanel = await page.locator('[title="Закрыть (Ctrl+Shift+Z)"]')
  .filter({ visible: true }).count() > 0;

if (hasModal) return { status: 'error', reason: 'модальная ошибка' };
if (formOpen && hasValidationPanel) return { status: 'error', reason: 'ошибка валидации' };
if (formOpen) return { status: 'error', reason: 'форма не закрылась' };
return { status: 'ok' };
```

---

## Запуск JS-сценариев

Команда `запусти сценарий <путь>.js` — выполнить файл через `browser_run_code`.

### Способ A (по умолчанию): clipboard loader

```powershell
Get-Content -LiteralPath <путь> -Raw | Set-Clipboard
```

Затем loader в `browser_run_code`:
```javascript
async (page) => {
  let src;
  try { src = await page.evaluate(() => navigator.clipboard.readText()); }
  catch (e) { return { ok: false, stage: 'clipboard', message: String(e) }; }

  if (!src || !src.includes('async (page)'))
    return { ok: false, stage: 'clipboard', message: 'Нет сценария в буфере' };

  let scenario;
  try { scenario = (0, eval)(`(\n${src}\n)`); }
  catch (e) { return { ok: false, stage: 'compile', message: e.message }; }

  try { return { ok: true, result: await scenario(page) }; }
  catch (e) { return { ok: false, stage: 'runtime', message: e.message, stack: e.stack }; }
}
```

### Способ B (fallback): прямой запуск

Если clipboard недоступен — прочитать файл, передать код напрямую в `browser_run_code`.

---

---

## Скрипты утилиты

Готовые скрипты в `scripts/` — включать в `browser_run_code` через `${read(...)}`.

### 1c-screenshot.js
Скриншоты + кеш селекторов (`.codex/1c-web-cache.json`):
- `screenshot1C(page, name, opts)` — скриншот в `playwright-screenshots/`, автоочистка > 7 дней
- `loadCache(baseUrl)` / `saveSelector(baseUrl, key, value)` — чтение/запись кеша (точечная нотация)
- `locatorWithCache(page, baseUrl, cacheKey, fallbacks[])` — пробует кеш → fallbacks → сохраняет найденный

### 1c-login.js (требует 1c-screenshot.js)
`login1C(page, baseUrl, user, password)` — логин через clipboard paste, пропускает если уже залогинен.

### 1c-open-object.js
- `openObject1C(page, baseUrl, metadataPath, guid)` — открыть объект по GUID
- `openList1C(page, baseUrl, metadataPath)` — открыть список

### 1c-snapshot.js (требует 1c-screenshot.js)
`snapshot1C(page, navigateTo?)` — собирает `visibleFields` (label+value без скриншота) + заголовок формы.

### 1c-fill-form.js
`fillForm1C(page, fields, options)` — заполняет поля формы через clipboard paste.

### Пример: открыть объект по GUID и прочитать поля

```javascript
async (page) => {
  // paste content of 1c-open-object.js
  // paste content of 1c-screenshot.js
  // paste content of 1c-snapshot.js
  return await snapshot1C(page,
    '<base-url>/e1cib/data/Справочник.Номенклатура?ref=<guid>'
  );
}
```

---

## Оптимизация

Подробные рекомендации — в `references/optimization.md`. Ключевое:

- **Один `browser_run_code` на всё задание** — не пошаговые вызовы
- **`Tab` перед DLB-кликом** — снимает фокус с поля ввода
- **`waitForTimeout(50)`** для dropdown — `waitFor` избыточен
- **JS-верификация внутри** — без screenshot
- **`browser_snapshot` только** при первом типе элемента или при ошибке
- При сбое цепочки → переключиться на пошаговые инструменты + `browser_snapshot`
