/**
 * 1C Web Client — Navigate + Snapshot in one call
 *
 * Навигация к объекту + снапшот за один browser_run_code вызов.
 * Использовать когда нужно ВИДЕТЬ форму, а не просто данные.
 * Для чтения данных предпочтительнее execute_query через 1c-ai-debug.
 *
 * Использование — снять снапшот текущей страницы:
 *   browser_run_code(code=`
 *     ${read('<skills-root>/web-session/scripts/1c-screenshot.js')}
 *     ${read('<skills-root>/web-session/scripts/1c-snapshot.js')}
 *     return await snapshot1C(page);
 *   `)
 *
 * Использование — перейти по URL и снять снапшот:
 *   browser_run_code(code=`
 *     ${read('<skills-root>/web-session/scripts/1c-screenshot.js')}
 *     ${read('<skills-root>/web-session/scripts/1c-snapshot.js')}
 *     return await snapshot1C(page, 'http://127.0.0.1/demo/e1cib/data/Справочник.Номенклатура?ref=<guid>');
 *   `)
 *
 * Возвращает: { url, title, formTitle, visibleFields }
 *   visibleFields — список видимых полей формы (label + value) для быстрого чтения без скриншота
 */
async function snapshot1C(page, navigateTo) {
  if (navigateTo) {
    await page.goto(navigateTo);
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForSelector('.v8-busy-indicator', { state: 'hidden', timeout: 8000 }).catch(() => {});
  }

  // Собираем видимые поля формы — экономит токены vs скриншот
  const fields = await page.evaluate(() => {
    const result = [];
    const fieldElems = document.querySelectorAll('.v8-form-field, [data-v8-field-caption]');
    fieldElems.forEach(el => {
      const label = el.querySelector('.v8-field-caption, label, [data-v8-field-caption]')?.textContent?.trim();
      const value = el.querySelector('input, textarea, .v8-display-value, .v8-field-value')?.value
        || el.querySelector('.v8-display-value, .v8-field-value')?.textContent?.trim();
      if (label) result.push({ label, value: value ?? '' });
    });
    return result.slice(0, 30); // Не больше 30 полей
  }).catch(() => []);

  const formTitle = await page.locator('.v8-form-title, .v8-title-panel .title-text').first()
    .textContent({ timeout: 2000 })
    .catch(() => null);

  return {
    url: page.url(),
    title: await page.title(),
    formTitle: formTitle?.trim() ?? null,
    visibleFields: fields  // Читаемые данные без скриншота — приоритет
  };
}
