const page = await getPage();
const user = process.env.CODEX_1C_USERNAME || '';
const password = process.env.CODEX_1C_PASSWORD || '';
const shell = page.locator('#themesCell_theme_0');
const userField = page.locator(
  'input[name="user"], input[name="username"], input[type="text"]'
).first();

if (!await shell.isVisible().catch(() => false)
    && await userField.isVisible({ timeout: 3000 }).catch(() => false)) {
  await userField.fill(user);
  const passwordField = page.locator(
    'input[name="pwd"], input[name="password"], input[type="password"]'
  ).first();
  await passwordField.fill(password);
  await page.locator(
    'button[type="submit"], input[type="submit"], button:has-text("Войти"), button:has-text("OK")'
  ).first().click();
}

await page.waitForSelector('#themesCell_theme_0', { timeout: 60000 });
await page.waitForTimeout(5000);
const state = await getFormState();
const visibleText = await page.locator('body').innerText();
const compilationFailure = /(ОшибкаКомпиляцииВстроенногоЯзыка|не определена\s*\((ПрочитатьJSON|ЗаписатьJSON)\))/i.test(visibleText);

if (state.errorModal) {
  throw new Error(`1C error modal after web-client startup: ${state.errorModal.message || 'unknown'}`);
}
if (compilationFailure) {
  throw new Error('Web-client startup contains a JSON compilation failure');
}

console.log(JSON.stringify({
  webClientLoaded: true,
  compilationFailure: false,
  errorModal: false,
  formCount: state.formCount,
  sectionPanelVisible: await shell.isVisible(),
}));
