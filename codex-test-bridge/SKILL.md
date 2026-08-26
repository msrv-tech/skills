---
name: codex-test-bridge
description: HTTP bridge-расширение для демо- и тестовых баз 1С. Используй когда нужно поставить или вызвать CodexTestBridge CFE вместо COM-подключения, получить метаданные по HTTP, создать/прочитать тестовые данные, выполнить запрос или проверить внешние отчеты и печатные формы без UI.
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
---

# /codex-test-bridge

Служебное расширение 1С, которое заменяет COM-подключение HTTP API для демо
и тестовых баз. Расширение публикует HTTP-сервис `codex-test`.

Не подключай bridge к боевым базам и не публикуй наружу: команды выполняются
серверным кодом 1С с повышенными возможностями.

## Что Лежит В Скилле

- `src/` - XML-исходники расширения
- `codex-test-bridge.cfe` - готовое собранное расширение
- `codex-test-bridge-legacy.cfe` - server-only вариант для старых режимов
  совместимости конфигурации
- `client.py` - Python CLI-клиент, который вызывает HTTP API и отключает proxy
- `scenario_runner.py` - headless runtime декларативных JSON-сценариев
- `scenario.schema.json` - схема сценария для IDE и ИИ-агентов
- `examples/` - готовые примеры сценариев
- `ui_worker.py` - изолированный запуск штатных TestClient/TestManager
- `ui-worker.example.json` - универсальный шаблон UI-worker только с env-плейсхолдерами
- `ui-worker.server.example.json` - шаблон серверной ИБ только с env-плейсхолдерами
- `ui-worker.cross-db.example.json` - раздельные целевая ИБ и ИБ TestManager
- `ui-worker.cross-db.credentials.example.json` - cross-db запуск существующими
  прикладными тестовыми пользователями через env
- `ui-scenario.schema.json` - схема нативного семантического UI DSL
- `UI_WORKER.md` - контракт управляющей обработки и backends
- `BRIDGE.md` - подробная спецификация endpoints и команд
- `scripts/build_cfe_linux.sh` - сборка CFE на Linux через `ibcmd`
- `scripts/build_cfe_windows.ps1` - сборка CFE на Windows через `ibcmd`
- `scripts/build_legacy_cfe_windows.ps1` - сборка server-only legacy CFE
- `scripts/run_cross_db_ui_with_bootstrap.py` - UI старой ИБ через отдельный
  full-bridge TestManager с одноразовыми пользователями
- `scripts/enable_vrd_windows.ps1` - включение HTTP-сервиса bridge в `default.vrd`
- `scripts/update_all_test_databases.py` - безопасное массовое обновление full/legacy
  CFE во всех серверных тестовых ИБ из приватного JSON-реестра
- `scripts/check_repository_hygiene.py` - проверка отсутствия стендовых
  подключений, логинов, приватных URL и локальных путей

## Безопасность Локальной Конфигурации

В репозитории допустимы только env-плейсхолдеры. Реальные URL bridge, сервер и
имя ИБ, файловый путь ИБ, логин и пароль храни в переменных окружения или secret
store CI. Локальные `*.local.json`, `.env`, отчёты, fixture-файлы и снимки
исключены через `.gitignore`.

Перед передачей или коммитом скилла выполни:

```powershell
python .\scripts\check_repository_hygiene.py
python -m unittest discover -s tests
```

UI-worker всегда маскирует `/P`, `/N`, `/S`, `/F` и соответствующие длинные
аргументы в JSON-отчёте, даже если локальный конфиг задаёт собственный список
секретных флагов.

## Выбор Варианта По Совместимости

- Для режима совместимости основной конфигурации `8.3.12` и выше используй
  `codex-test-bridge.cfe`. Он содержит HTTP bridge и нативный UI-worker.
- Для `8.3.11` и ниже используй `codex-test-bridge-legacy.cfe`. Он содержит весь
  HTTP API, но не содержит `uiJob*`, TestManager, общего модуля, роли и регистра
  UI-заданий: эти объекты запрещены самой платформой в старых режимах.
- UI старой ИБ не теряется: запускай её как `/TestClient`, а `/TestManager` — в
  отдельной тестовой ИБ с `codex-test-bridge.cfe` по шаблону
  `ui-worker.cross-db.example.json`. Конфигурации client и manager могут различаться.
- Не повышай режим совместимости основной конфигурации ради bridge.

Full-сборка намеренно не задаёт `DefaultRoles` и не содержит собственной роли:
это свойство корневой конфигурации нельзя переопределять при совместимости
`8.3.13` и ниже. Bridge работает под правами пользователя тестовой ИБ; используй
отдельного пользователя с достаточными правами. На реальной конфигурации с
режимом `8.3.12` подтверждены `uiJobCreate/uiJobDelete` и headless
TestManager/TestClient.

Если выданные тестовые логины не проходят, не сохраняй новые пароли в JSON.
Для доверенных тестовых баз используй
`scripts/run_cross_db_ui_with_bootstrap.py --allow-bootstrap-user`: он создаёт
случайных скрытых пользователей со всеми ролями на время одного запуска и
обязательно удаляет их. После запуска проверь отсутствие пользователей с
префиксами `ctb_ui_target_` и `ctb_ui_manager_` и процессов из run id.

Пользователь платформы не всегда автоматически становится пользователем
прикладной конфигурации. При диалоге БСП об ошибке авторизации не нажимай
`Завершить работу` и не помечай тест как skip: используй credentials-шаблон с
существующим пользователем, зарегистрированным в приложении.

UI-worker по умолчанию добавляет `/DisableStartupDialogs`,
`/DisableStartupMessages`, `/DisableSplash` и закрывает только безопасные
прикладные диалоги (`Продолжить`, `ОК`, `Закрыть`, `Пропустить`, `Позже`,
`Отмена`). Не добавляй в безопасный список `Да`, `Нет`, запись, проведение или
завершение сеанса. ДО через cross-db TestManager — обычный UI-тест, не
диагностический skip.

Обе сборки используют один исходный модуль HTTP-сервиса. Legacy-скрипт удаляет
только UI-команды и несовместимые метаданные, затем обязательно выполняет
серверную проверку модулей Designer.

При массовом обновлении из локального реестра ИБ не выводи значения подключения
и учётные данные. После установки каждой сборки проверь два маршрута через
клиент без proxy: `GET /health` и `POST /command` с `{"command":"health"}`.
На Windows всегда читай `test-databases.json` с явным `-Encoding UTF8`.
Windows PowerShell 5.1 иначе может исказить кириллический логин, что выглядит
как несуществующий пользователь ИБ или прикладной диалог авторизации.

Массовое обновление выполняется одной командой. Скрипт читает реестр как UTF-8,
определяет режим совместимости по локальному `Configuration.xml`, выбирает full
для 8.3.12+ и legacy для 8.3.11 и ниже, устанавливает через одноразового скрытого
пользователя и проверяет оба health-маршрута. Значения реестра в вывод не попадают:
Транзиентный отказ Designer или публикации повторяется до трёх раз.
До и после установки проверяется отсутствие оставшихся `ctb_bootstrap_`
пользователей; при обнаружении чужая возможная установка не удаляется автоматически.

```powershell
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex' }
$skillsRoot = Join-Path $codexRoot 'skills'
$registry = & (Join-Path $skillsRoot 'test-databases\scripts\resolve-registry.ps1')
python (Join-Path $skillsRoot 'codex-test-bridge\scripts\update_all_test_databases.py') --allow-bootstrap-user `
  --registry $registry --platform $env:CODEX_1C_EXECUTABLE
```

## Установка Расширения В Файловую Базу

Предпочтительный путь - через `ibcmd`, с отдельным `--data` каталогом:

```powershell
& $env:CODEX_IBCMD config --data $env:CODEX_1C_BUILD_DATA --database-path $env:CODEX_1C_DATABASE_PATH load --extension CodexTestBridge --force .\codex-test-bridge.cfe
& $env:CODEX_IBCMD config --data $env:CODEX_1C_BUILD_DATA --database-path $env:CODEX_1C_DATABASE_PATH check --extension CodexTestBridge --force
& $env:CODEX_IBCMD config --data $env:CODEX_1C_BUILD_DATA --database-path $env:CODEX_1C_DATABASE_PATH apply --extension CodexTestBridge --force --dynamic=disable --session-terminate=force
```

Учётные данные и параметры подключения получай из защищённых переменных среды
или secret store CI. Не записывай их в файлы скилла, команды документации,
отчёты и логи.

## Веб-Публикация

Bridge доступен только если опубликованы HTTP-сервисы расширений. В `default.vrd`
должно быть:

```xml
<httpServices publishByDefault="true" publishExtensionsByDefault="true">
  <service name="CodexTestBridge" rootUrl="codex-test" enable="true"
           reuseSessions="dontuse" sessionMaxAge="20"/>
</httpServices>
```

Обычный `web-publish` генерирует безопасную публикацию без HTTP-сервисов
расширений. Для bridge после публикации базы включи сервис отдельным helper:

```powershell
.\scripts\enable_vrd_windows.ps1 -VrdPath $env:CODEX_1C_VRD_PATH
```

Базовые URL:

```text
http://<host>/<publication>/hs/codex-test/health
http://<host>/<publication>/hs/codex-test/command
```

## Клиент

`client.py` отключает proxy-переменные для локальных запросов.

```powershell
$bridgeUrl = $env:CODEX_1C_BRIDGE_URL
python .\client.py --base-url $bridgeUrl health
```

Полезные команды:

```powershell
# Метаданные
python .\client.py --base-url $bridgeUrl metadata --sections catalogs,documents

# Описание объекта
python .\client.py --base-url $bridgeUrl describe catalog Контрагенты

# Запрос
python .\client.py --base-url $bridgeUrl query "ВЫБРАТЬ ПЕРВЫЕ 10 Ссылка, Наименование ИЗ Справочник.Контрагенты" --limit 10

# Выполнить серверный BSL-код
python .\client.py --base-url $bridgeUrl execute-bsl "РезультатВыполнения = ТекущаяДата();"

# Вызвать экспортный метод общего модуля
python .\client.py --base-url $bridgeUrl call-common-module ОбщегоНазначения ЗначениеРеквизитаОбъекта --params "[{`"type`":`"CatalogRef`",`"name`":`"Контрагенты`",`"uuid`":`"00000000-0000-0000-0000-000000000000`"},`"Наименование`"]"

# Выполнить серверный BSL-код
python .\client.py --base-url http://localhost:9091/demo1c/hs/codex-test execute-bsl "РезультатВыполнения = ТекущаяДата();"

# Вызвать экспортный метод общего модуля
python .\client.py --base-url http://localhost:9091/demo1c/hs/codex-test call-common-module ОбщегоНазначения ЗначениеРеквизитаОбъекта --params "[{`"type`":`"CatalogRef`",`"name`":`"Контрагенты`",`"uuid`":`"00000000-0000-0000-0000-000000000000`"},`"Наименование`"]"

# Создать/обновить объект
python .\client.py --base-url $bridgeUrl write-object catalog Контрагенты --fields "{`"Наименование`":`"Codex HTTP smoke`"}"

# Выполнить headless JSON-сценарий и сохранить полный отчет
python .\client.py --base-url $bridgeUrl run-scenario .\examples\smoke.scenario.json --report .\artifacts\smoke-report.json
```

Для нестабильных или долгих операций настрой `retry` у шага и общий HTTP-таймаут:

```powershell
python .\client.py --base-url $bridgeUrl --timeout 120 run-scenario .\examples\smoke.scenario.json

# Запустить каталог *.scenario.json и сформировать JSON + JUnit
python .\client.py --base-url $bridgeUrl run-suite .\examples --report .\artifacts\suite.json --junit .\artifacts\junit.xml
```

Для обязательной проверки управляемой формы без окон на пользовательском
рабочем столе используй нативный UI-worker:

```powershell
python .\client.py run-ui .\server.example.invalid.json .\examples\native-ui-smoke.ui.json --artifact-dir .\artifacts\smoke --report .\artifacts\smoke\worker.json
```

На Windows backend `auto` создаёт невидимый Win32 desktop, на Linux запускает
Xvfb. Формы открывай без меню действием `openNavigationLink` с прямой ссылкой
`e1cib/...` и `targetForm`. Для ссылки на конкретный объект можно передать
`uuid`, `kind: catalog|document` и `metadataName`: worker сам сформирует ref в
порядке групп UUID 4-5-3-2-1. Навигационная команда после принятия выполняется
ровно один раз; `attempts` повторяет только отвергнутую команду, а
`targetForm.timeout` ждёт новую форму и переживает временную занятость TestClient.
Для тяжёлых форм используется штатный wait платформы; `pollingInterval` по
умолчанию равен 5 секундам. При сбое смотри `beforeNavigation` в диагностике:
он сохраняется до возможной потери соединения.
Следи за `progress.json`/консольным heartbeat, краткий итог читай из
`summary.json`, а полную диагностику — из `ui-diagnostics.json`.
Для ссылочных полей используй нативное действие `selectReference` со
стратегией `auto`, `dropdownExact`, `typeAhead` или `choiceForm`; UIA `setValue` ссылку
в модели формы не устанавливает. Для неизвестной таблицы выбора сначала вызови
`openChoice` и `inspectTable`, затем передай полученные ключи колонок в `row`.
UI-формат содержит только атомарные TestClient-действия: не добавляй в него
переменные, условия, циклы, fixtures или cleanup — это уже покрыто серверным
bridge и `scenario_runner.py`.
Подробности и JSON-примеры см. в
`UI_WORKER.md`.

## Сборка CFE Из Исходников

Windows:

```powershell
.\scripts\build_cfe_windows.ps1 -PlatformPath $env:CODEX_1C_PLATFORM
.\scripts\build_legacy_cfe_windows.ps1 -PlatformPath $env:CODEX_1C_PLATFORM
```

Linux:

```bash
IBCMD="$CODEX_IBCMD" sh ./scripts/build_cfe_linux.sh
```

## Основные Команды API

Все команды, кроме `health`, отправляются POST-запросом на `/command`.

- `Health` - проверка доступности
- `Metadata` - список объектов метаданных
- `Describe` - реквизиты и табличные части объекта
- `Query` - выполнение запроса 1С
- `ExecuteBSL` - выполнение серверного кода через `Выполнить()`
- `CallCommonModule` - вызов экспортного метода общего модуля
- `WriteObject` - создать или обновить элемент справочника/документ
- `GetObject` - получить объект по UUID
- `DeleteObject` - поставить или снять пометку удаления
- `RenderExternalPrintForm` - серверная проверка внешней печатной формы
- `RenderExternalReport` - серверная проверка внешнего отчета

Для многошаговых проверок используй `run-scenario`: формат сценария, подстановки,
assertions, retry и cleanup описаны в `BRIDGE.md`.

Подробности и JSON-примеры см. в `BRIDGE.md`.
