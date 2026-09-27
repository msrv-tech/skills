# Оптимизация работы с 1С веб-клиентом

## Таймаут Playwright MCP

По умолчанию — **5000ms**. Настраивается в `.mcp.json`:

```json
{
  "playwright": {
    "command": "npx",
    "args": ["@playwright/mcp@latest", "--timeout", "1000"]
  }
}
```

Таймаут — максимальное ожидание элемента, не пауза. Если элемент найден за 30ms — действие за 30ms.

| Ситуация | Таймаут |
|----------|---------|
| Лёгкая база, быстрый сервер | 100–200ms |
| Средняя нагрузка | 300–500ms |
| Тяжёлая база, медленный сервер | 700–1500ms |

## Стратегия: максимальная цепочка

**Один `browser_run_code` на всё задание.** Несколько объектов, навигация, циклы — всё в одном вызове.

| Подход | MCP-вызовов | Когда |
|--------|-------------|-------|
| Пошаговый | ~11 на элемент | Только при сбое для диагностики |
| Объединённый | 1 на задание | По умолчанию |
| Цикл | 1 на N элементов | Однотипные элементы |

**При сбое цепочки** — НЕ повторять. Переключиться на пошаговые: `browser_snapshot` → `browser_click` / `browser_press_key`. Найти причину, исправить, вернуться к цепочке.

## Типы полей выбора

Все кнопки выбора в 1С — суффикс `_DLB`. Разница в результате клика:

```javascript
await page.locator('[id$="_ИмяПоля_DLB"]').click();
await page.waitForTimeout(100);

if (await page.locator('#editDropDown').count() > 0) {
  await page.locator('#editDropDown').getByText('Значение').click();
} else {
  await page.getByTitle('Выбрать значение (Ctrl+Enter)').waitFor();
  await page.getByText('Значение').click();
  await page.getByTitle('Выбрать значение (Ctrl+Enter)').click();
}
```

**Почему не `getByTitle('Выбрать из списка')`:** при нескольких формах — `strict mode violation`.

## Рекомендуемый паттерн создания элемента

```javascript
async (page) => {
  // 1. Создать
  await page.locator('[id$="_ФормаКоманднаяПанель"]')
    .getByTitle('Создать новый элемент списка (Ins)').click();

  // 2. Ждать форму
  const nameInput = page.getByRole('textbox', { name: 'Наименование:' });
  await nameInput.waitFor({ timeout: 2000 });

  // 3. Заполнить наименование
  await page.evaluate((v) => navigator.clipboard.writeText(v), 'Название');
  await nameInput.click();
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Control+V');

  // 4. Tab перед DLB — снимает фокус
  await page.keyboard.press('Tab');
  await page.waitForTimeout(50);

  // 5. DLB
  await page.locator('[id$="_ВидАттракциона_DLB"]').click();
  await page.waitForTimeout(50);
  await page.locator('#editDropDown').getByText('Экстремальный').click();
  await page.waitForTimeout(50);

  // 6. Сохранить
  await page.keyboard.press('Control+Enter');
  await page.waitForTimeout(800);

  // 7. JS-верификация
  const hasModal = await page.locator('.modalSurface').count() > 0;
  const formOpen = await page.getByRole('textbox', { name: 'Наименование:' }).count() > 0;
  const hasValidationPanel = await page.locator('[title="Закрыть (Ctrl+Shift+Z)"]')
    .filter({ visible: true }).count() > 0;
  if (hasModal) return { status: 'error', reason: 'модальная ошибка' };
  if (formOpen && hasValidationPanel) return { status: 'error', reason: 'ошибка валидации' };
  if (formOpen) return { status: 'error', reason: 'форма не закрылась' };
  return { status: 'ok', element: 'Название' };
}
```

## Антипаттерны

```javascript
// ПЛОХО: хардкод номера формы
await page.locator('[id="form40_ВидНоменклатуры_DLB"]').click();
// ХОРОШО: суффиксный селектор
await page.locator('[id$="_ВидНоменклатуры_DLB"]').click();

// ПЛОХО: screenshot для проверки
await page.screenshot({ path: 'verify.png' });
// ХОРОШО: JS-верификация (0 токенов)
const hasError = await page.locator('.modalSurface').count() > 0;

// ПЛОХО: waitForTimeout без причины
await page.waitForTimeout(300);
await page.locator('[id$="_DLB"]').click();
// ХОРОШО: ждать элемент-индикатор
await page.getByRole('textbox', { name: 'Наименование:' }).waitFor();

// OK: waitForTimeout когда нет индикатора (форма закрылась)
await page.keyboard.press('Control+Enter');
await page.waitForTimeout(800);
```

## Когда browser_snapshot

- **Обязательно:** первый элемент нового типа (изучить форму)
- **Обязательно:** при ошибке или неожиданном поведении
- **Не нужно:** массовое создание однотипных элементов
- **Не нужно:** между заполнениями внутри `browser_run_code`
