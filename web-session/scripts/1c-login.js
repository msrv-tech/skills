/**
 * 1C Web Client — Login
 *
 * Логинится в 1С веб-клиент. Пропускает если уже залогинен.
 *
 * Использование (с кешем селекторов):
 *   browser_run_code(code=`
 *     ${read('<skills-root>/web-session/scripts/1c-screenshot.js')}
 *     ${read('<skills-root>/web-session/scripts/1c-login.js')}
 *     return await login1C(page, 'http://127.0.0.1/demo', 'test-user', process.env.CODEX_1C_PASSWORD);
 *   `)
 *
 * Возвращает: { loggedIn, url, title, alreadyLoggedIn }
 */
async function login1C(page, baseUrl, user, password) {
  await page.goto(baseUrl + '/');
  await page.waitForLoadState('networkidle', { timeout: 15000 });

  const url = page.url();
  const title = await page.title();

  // Проверяем — уже залогинены?
  const BASE = baseUrl;
  const userLoc = typeof locatorWithCache !== 'undefined'
    ? await locatorWithCache(page, BASE, 'login.userInput',
        ['input[name="user"]', 'input[name="username"]', 'input[type="text"]'])
    : page.locator('input[name="user"], input[name="username"], input[type="text"]').first();

  const isLoginPage = userLoc && await userLoc.isVisible({ timeout: 2000 }).catch(() => false);

  if (!isLoginPage) {
    return { loggedIn: true, alreadyLoggedIn: true, url, title };
  }

  // Логин через clipboard paste
  await userLoc.click();
  await page.keyboard.press('Control+A');
  await page.evaluate((v) => navigator.clipboard.writeText(v), user);
  await page.keyboard.press('Control+V');

  const pwdField = typeof locatorWithCache !== 'undefined'
    ? await locatorWithCache(page, BASE, 'login.passwordInput',
        ['input[name="pwd"]', 'input[name="password"]', 'input[type="password"]'])
    : page.locator('input[name="pwd"], input[name="password"], input[type="password"]').first();

  await pwdField.click();
  await page.keyboard.press('Control+A');
  await page.evaluate((v) => navigator.clipboard.writeText(v), password);
  await page.keyboard.press('Control+V');

  const submitBtn = typeof locatorWithCache !== 'undefined'
    ? await locatorWithCache(page, BASE, 'login.submitButton',
        ['button[type="submit"]', 'input[type="submit"]', 'button:has-text("Войти")', 'button:has-text("OK")'])
    : page.locator('button[type="submit"], input[type="submit"], button:has-text("Войти"), button:has-text("OK")').first();
  await submitBtn.click();

  await page.waitForLoadState('networkidle', { timeout: 20000 });

  return {
    loggedIn: true,
    alreadyLoggedIn: false,
    url: page.url(),
    title: await page.title()
  };
}
