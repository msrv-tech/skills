/**
 * 1C Web Client — Fill Form Fields
 *
 * Заполняет поля формы через clipboard paste (единственный надёжный способ в 1С).
 * ВАЖНО: fill(), type(), pressSequentially() НЕ работают в 1С веб-клиенте.
 *
 * ВНИМАНИЕ: Предпочтительнее использовать 1c-ai-debug create_catalog_item / create_document.
 * Этот скрипт — резервный вариант когда нужно именно через UI.
 *
 * Использование:
 *   browser_run_code(code=`
 *     ${read('<skills-root>/web-session/scripts/1c-fill-form.js')}
 *     return await fillForm1C(page, {
 *       'Наименование': 'Тест-001',
 *       'Код': '001'
 *     }, { save: true });
 *   `)
 *
 * Возвращает: { saved, url, errors }
 */
async function fillForm1C(page, fields, options = {}) {
  const { save = false, waitMs = 300 } = options;
  const errors = [];

  for (const [fieldName, value] of Object.entries(fields)) {
    try {
      // 1С: ищем caption, затем соседний input
      const caption = page.locator(`.v8-field-caption:has-text("${fieldName}")`)
        .or(page.locator(`label:has-text("${fieldName}")`))
        .first();

      const field = caption.locator('..').locator('input, textarea').first();
      const isVisible = await field.isVisible({ timeout: 2000 });

      if (isVisible) {
        await field.click({ force: true });
        await page.waitForTimeout(waitMs);
        // Clipboard paste — единственный надёжный способ в 1С
        await page.keyboard.press('Control+A');
        await page.evaluate((v) => navigator.clipboard.writeText(v), String(value));
        await page.keyboard.press('Control+V');
        await page.waitForTimeout(waitMs);
      } else {
        errors.push(`Поле не найдено: ${fieldName}`);
      }
    } catch (e) {
      errors.push(`Ошибка при заполнении "${fieldName}": ${e.message}`);
    }
  }

  if (save) {
    await page.keyboard.press('Control+S');
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(500);
  }

  return {
    saved: save,
    url: page.url(),
    errors
  };
}
