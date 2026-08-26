/**
 * 1C Web Client — Open Object By Reference
 *
 * Открывает объект 1С по GUID напрямую через URL.
 * Намного быстрее чем навигация через меню.
 *
 * 1С URL схема:
 *   Справочник: /e1cib/data/Справочник.ИмяСправочника?ref=<guid>
 *   Документ:   /e1cib/data/Документ.ИмяДокумента?ref=<guid>
 *
 * Использование:
 *   browser_run_code(code=`
 *     ${read('<skills-root>/web-session/scripts/1c-open-object.js')}
 *     return await openObject1C(page,
 *       'http://127.0.0.1/demo',
 *       'Справочник.Номенклатура',
 *       'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
 *     );
 *   `)
 *
 * Возвращает: { url, title, formTitle }
 */
async function openObject1C(page, baseUrl, metadataPath, guid) {
  const url = `${baseUrl}/e1cib/data/${metadataPath}?ref=${guid}`;
  await page.goto(url);
  await page.waitForLoadState('networkidle', { timeout: 15000 });

  await page.waitForSelector('.v8-busy-indicator, .v8-progress-bar', { state: 'hidden', timeout: 10000 })
    .catch(() => {});

  const formTitle = await page.locator('.v8-form-title, h1, .title-text').first()
    .textContent({ timeout: 3000 })
    .catch(() => null);

  return {
    url: page.url(),
    title: await page.title(),
    formTitle: formTitle?.trim() ?? null
  };
}

/**
 * Открыть список объектов (catalog list / document list)
 *
 * Использование:
 *   return await openList1C(page, 'http://127.0.0.1/demo', 'Справочник.Номенклатура');
 */
async function openList1C(page, baseUrl, metadataPath) {
  const url = `${baseUrl}/e1cib/list/${metadataPath}`;
  await page.goto(url);
  await page.waitForLoadState('networkidle', { timeout: 15000 });

  await page.waitForSelector('.v8-busy-indicator', { state: 'hidden', timeout: 10000 })
    .catch(() => {});

  return {
    url: page.url(),
    title: await page.title()
  };
}
