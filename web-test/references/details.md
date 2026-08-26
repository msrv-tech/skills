# Additional Details

Moved from web-test/SKILL.md to keep the skill lightweight.

## Common patterns

### Create and save a document

```js
await navigateSection('Продажи');
await openCommand('Заказы клиентов');
await clickElement('Создать');
await fillFields({ 'Организация': 'Конфетпром', 'Контрагент': 'Альфа' });
await fillTableRow({ 'Номенклатура': 'Бумага', 'Количество': '10' }, { tab: 'Товары', add: true });
await clickElement('Провести и закрыть');
```

### Open item from list

```js
await clickElement('КП00-000227', { dblclick: true });
// Always use { dblclick: true } — single click only selects the row
```

### Work with hierarchical lists

```js
await filterList('Конфетпром');                               // flatten + search
await clickElement('Конфетпром ООО', { dblclick: true });     // open
await closeForm();
await unfilterList();                                          // restore hierarchy
```

### Generate and read a report

```js
// Fill report filters using readable labels
await fillFields({ 'Склад': 'Основной склад' });
await clickElement('Сформировать');
await wait(5);
const report = await readSpreadsheet();
console.log('Title:', report.title);
console.log('Data rows:', report.data?.length);
```

### Drill-down report cells

```js
// Generate report
await clickElement('Сформировать');
await wait(5);
const report = await readSpreadsheet();

// Double-click cell to open drill-down (uses coordinates from readSpreadsheet)
await clickElement({ row: 0, column: 'К6' }, { dblclick: true });
// Modal dialog "Выбор поля" opens
await clickElement('Регистратор');
await clickElement('Выбрать');
await wait(10);
const drilldown = await readSpreadsheet();
```

### Work with multi-grid forms

Some forms have multiple grids (e.g. "Входящие" and "Исходящие" tables on a single form). Without `table`, buttons like "Добавить" hit the first match and `readTable` reads the first grid — which may not be the one you need.

**Step 1 — discover tables** via `getFormState()`:
```js
const form = await getFormState();
// form.tables = [
//   { name: "ДеревоБизнесПроцессов", columns: ["Полный код", "Бизнес-процесс"], rowCount: 21 },
//   { name: "Входящие", label: "Входящие", columns: ["Объект", "Бизнес-процесс источник", ...], rowCount: 1 },
//   { name: "Исходящие", label: "Исходящие", columns: ["Объект", "Бизнес-процесс приемник", ...], rowCount: 1 }
// ]
```

**Step 2 — use `table` name** in any grid operation:
```js
// Read specific table
const t = await readTable({ table: 'Исходящие' });

// Add row — fillTableRow with add:true already clicks the right "Добавить" button
await fillTableRow({ 'Объект': 'БДДС' }, { table: 'Исходящие', add: true });

// Or click buttons separately
await clickElement('Добавить', { table: 'Входящие' });

// Delete from specific table
await deleteTableRow(0, { table: 'Исходящие' });
```

Table matching accepts both technical name (`tables[].name`) and visual label (`tables[].label`). Label is the group title shown on screen — useful when working from screenshots. Name match takes priority over label match.

### Keyboard shortcuts

```js
const page = await getPage();
await page.keyboard.press('F8');  // example: create new item in focused reference field
```

| Key | Context | Action |
|-----|---------|--------|
| `F8` | Reference field focused | Create new catalog item |
| `Shift+F4` | Any input field focused | Clear field value (auto via `''`/`null` in fillFields/selectValue/fillTableRow) |
| `F4` | Reference field focused | Open selection form |
| `Alt+F` | List/table form | Open advanced search dialog |

### Closing forms — which method to use

| Goal | Method |
|------|--------|
| Post & close document | `clickElement('Провести и закрыть')` |
| Save & close catalog | `clickElement('Записать и закрыть')` |
| Close without saving | `closeForm({ save: false })` |
| Close and save | `closeForm({ save: true })` |
| Close (manual confirm) | `closeForm()` — returns `confirmation` if dialog appears |

## Exec response format

```json
{ "ok": true, "output": "...console.log output...", "elapsed": 3.2 }
```

On error (auto-screenshot taken):
```json
{ "ok": false, "error": "Element not found", "output": "...", "screenshot": "error-shot.png", "elapsed": 1.5 }
```

## Avoiding loops

- **Max 2 attempts per operation.** If an action fails twice with the same approach — stop and report to the user
- **Not found = not found.** If `filterList` returns 0 rows or `readTable` is empty after filtering — the item likely doesn't exist in this database. Don't retry the same search 5 times with slight variations
- **Try a different approach, not the same one.** Couldn't find via section navigation? Try `navigateLink`. Couldn't find via simple search? Try advanced search with a specific field. But don't repeat the same method
- **Report partial results.** If you found the list but not the specific item — say so. Show what IS available instead of silently retrying

## Important notes

- **Headed mode** — 1C requires visible browser, no headless
- **Startup time** — 1C loads 30-60s on initial connect (built into `start`)
- **Fuzzy matching** — all name lookups: exact > startsWith > includes
- **Clipboard paste** — all text fields filled via Ctrl+V (triggers 1C events properly)
- **Cyrillic in bash** — use `cat <<'SCRIPT' | node $RUN exec -` to avoid escaping issues
- **Non-breaking spaces** — 1C uses `\u00a0` instead of regular spaces. All matching is normalized internally
- **Section panel display** — `navigateSection()` works with any panel position (side, top) but requires "Picture and text" or "Text" display mode. Icon-only mode is not supported — API cannot read section names from icons alone

