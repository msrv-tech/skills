/**
 * Скан навигационного меню 1С веб-клиента.
 * Запустить через browser_run_code. Результат записать в .claude/1c-nav.json (Write tool).
 *
 * Источник: RooLee10/1c-web-session (MIT)
 */
async (page) => {
  const nav = {
    url: page.url().split('?')[0],
    scannedAt: new Date().toISOString(),
    sections: []
  };

  // Читаем разделы без клика — перебираем по инкрементальному ID
  let i = 0;
  while (await page.locator(`#themesCell_theme_${i}`).count() > 0) {
    const el = page.locator(`#themesCell_theme_${i}`);
    const name = (await el.innerText()).trim();
    nav.sections.push({ name, id: `#themesCell_theme_${i}`, items: [] });
    i++;
  }

  // Для каждого раздела: открываем меню, читаем пункты
  for (const section of nav.sections) {
    await page.locator(section.id).click();
    await page.waitForTimeout(400);

    const itemEls = await page.locator('[id^="cmd_"][id$="_txt"]')
      .filter({ visible: true }).all();

    for (const item of itemEls) {
      const id = '#' + await item.getAttribute('id');
      const name = (await item.innerText()).trim();
      if (name) section.items.push({ name, id });
    }
  }

  await page.keyboard.press('Escape');
  await page.waitForTimeout(200);

  return nav;
}
