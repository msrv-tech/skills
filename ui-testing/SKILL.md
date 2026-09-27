---
name: ui-testing
description: >-
  Playwright-сессии и браузерные UI-тесты веб-клиента 1С; нативный UI остаётся в codex-test-bridge.
allowed-tools:
  - Read
  - Glob
  - Bash
---

# ui-testing

Выбери один режим по намерению пользователя и полностью прочитай только его
инструкцию. Не загружай остальные references без необходимости.
Для нативного TestClient/TestManager используй `codex-test-bridge`.

| Режим | Назначение | Детали | Исполняемые точки входа |
|---|---|---|---|
| `session` | Управлять интерактивной web-сессией | [инструкция](references/session.md) | `scripts/session-login.js`, `scripts/session-snapshot.js` |
| `test` | Выполнить браузерный тест | [инструкция](references/test.md) | `scripts/web-run.mjs` |
| `scaffold` | Создать поддерживаемый Playwright-тест | [инструкция](references/scaffold.md) | — |

После изменяющего режима выполни профильную валидацию, если инструкция режима
не включает равнозначную проверку. Скрипты запускай из этого доменного каталога.
