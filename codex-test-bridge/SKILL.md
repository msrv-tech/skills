---
name: codex-test-bridge
description: HTTP bridge-расширение для демо- и тестовых баз 1С. Используй когда нужно поставить или вызвать CodexTestBridge CFE вместо COM-подключения, получить метаданные по HTTP, создать/прочитать тестовые данные, выполнить запрос, прочитать журнал регистрации или проверить внешние отчеты и печатные формы без UI.
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
- `scripts/install_cfe_linux.sh` - строгая установка CFE в файловую ИБ
- `scripts/enable_vrd_linux.py` - атомарное включение bridge в существующем VRD
- `scripts/linux_flow.sh` - Linux doctor и полный smoke от сборки до Xvfb
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

```bash
python3 ./scripts/check_repository_hygiene.py
python3 -m unittest discover -s tests
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

Для UI-теста базы из приватного реестра сначала используй существующие `User` и
`Password` через `scripts/run_ui_from_test_database.py`. Скрипт не выводит их и
восстанавливает переменные окружения после запуска. Это основной путь для БП и
других конфигураций с первичной настройкой пользователя.

Если выданные тестовые логины не проходят, не сохраняй новые пароли в JSON.
Для доверенных тестовых баз используй
`scripts/run_cross_db_ui_with_bootstrap.py --allow-bootstrap-user`: он создаёт
случайных скрытых пользователей со всеми ролями на время одного запуска и
обязательно удаляет их. После запуска проверь отсутствие пользователей с
префиксами `ctb_ui_target_` и `ctb_ui_manager_` и процессов из run id.
Не применяй bootstrap по умолчанию в конфигурациях, где первый вход нового
пользователя запускает обновление данных: оборванный клиент может оставить
серверный сеанс обновления и заблокировать последующие TestClient.

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

На Linux используй строгий install helper. `CODEX_IBCMD` должен указывать на
исполняемый файл `ibcmd` либо на каталог версии платформы 8.5. Для каталога
поддерживаются `<version>/ibcmd` и `<version>/bin/ibcmd`; если существуют оба,
нужно указать точный executable. Автоматического перехода на Designer нет:

```bash
IBCMD="$CODEX_IBCMD" \
IB_PATH="$CODEX_1C_DATABASE_PATH" \
IB_USER="$CODEX_1C_USERNAME" \
IB_PASSWORD="${CODEX_1C_PASSWORD:-}" \
CFE=./codex-test-bridge.cfe \
DATA="$CODEX_1C_BUILD_DATA" \
./scripts/install_cfe_linux.sh
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

Linux:

```bash
python3 ./scripts/enable_vrd_linux.py "$CODEX_1C_VRD_PATH"
apache2ctl configtest
systemctl reload apache2
```

Linux helper атомарно изменяет только указанный VRD и сохраняет остальные
HTTP-сервисы. Сам helper и полный flow не вызывают `sudo`: пользователь,
запускающий их, уже должен иметь права на VRD и reload Apache. Ошибка прав
завершает flow, а не скрывается.

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

# Журнал регистрации
python .\client.py --base-url $bridgeUrl event-log --minutes 30 --level error --limit 50

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

На Windows backend `auto` создаёт невидимый Win32 desktop; только этот backend
поддерживает UIA и `uiaBeforeSteps`. На Linux backend запускает Xvfb и работает
через штатные TestClient/TestManager: UIA bootstrap недоступен и не
эмулируется. Ошибка выбранного backend должна завершать запуск без
автоматического переключения. Обычные формы открывай без меню действием
`openForm`: передай
`metadataKind` (`catalog`, `document`, `task`, `dataProcessor`, `report`, `commonForm`),
`metadataName`, `formName` и обязательный `targetForm`. Для обработки есть
короткая форма `openDataProcessor`. Эти действия выполняют штатный клиентский
`ОткрытьФорму()` и не требуют подбирать `e1cib`-ссылку. `openNavigationLink`
оставляй только для действительно навигационных ссылок; у него также обязателен
`targetForm` с `formName`, `objectName` или `title`, а форма ошибки навигации
всегда означает failed. Для задачи, созданной server hook в hybrid-сценарии,
используй `openForm` с `metadataKind: "task"`, `metadataName`, `uuid`,
`formName` и `targetForm`: Bridge передаст типизированную ссылку через
временное хранилище TestClient и откроет форму штатным `ОткрытьФорму()`.
Если задача должна открыться именно в назначенной форме выполнения, используй
`openTaskExecutionForm` с `uuid` и `targetForm`: bridge запрашивает штатную
`ФормаВыполненияЗадачи()` и открывает возвращённые имя формы и параметры. Не
нажимай для этого декорацию «Перейти в форму…» и не используй UIA. Для
`openNavigationLink` конкретного объекта можно передать
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
`openChoice` и `inspectTable`, затем передай в `row` ключи `columns[].name`
(не заголовки с пробелами, если можно). `selectTableRow` по умолчанию вызывает
`Выбрать()`; для позиционирования без открытия карточки используй `select: false`.
Строка поиска динамического списка вводится через `inputText` с
`elementType: "addition"`. Если выбранное дополнение свёрнуто или не принимает
`ВвестиТекст`, bridge ищет на форме другие `ТестируемоеДополнениеЭлементаФормы`
и вводит в первое, которое принимает текст; при необходимости нажимает соседние
дополнения (управление поиском) без зашитых имён БСП. Поиск подсвечивает ячейки
HTML — `selectTableRow`/`assertTableRow` сравнивают текст без тегов, пробуют
ключи колонок и по `name`, и по `title`, и обходят строки, если штатный
`ПерейтиКСтроке` не совпал. `waitForm` с
`newForm: true` ждёт новую форму.
`onPrompt: discard|save|cancel` сам нажимает Нет/Да/Отмена.
Для ссылочной ячейки табличной части передавай целевые `table`, `row`, `field`,
а таблицу и строку формы выбора — отдельно в `choiceTable`, `choiceRow`.
`selectReference` сам вызывает `ИзменитьСтроку()`, завершает строку через
`ЗакончитьРедактированиеСтроки(Ложь)` и ждёт `onChangeWait` секунд. Для текста
ячейки используй `inputTableCell`, для проверки — `assertField` с теми же
`table`/`row`/`field`. Отдельно активировать страницу обычно не нужно: bridge
активирует целевую таблицу. Табличный `openChoice` оставляет строку в режиме
редактирования и предназначен для разведки; атомарный выбор выполняй через
`selectReference`.
Для ссылочной ячейки со `strategy: choiceForm` обязательно передавай связанную
`choiceForm`: bridge открывает её штатным `Поле.Выбрать()` у редактора ячейки.
Не заменяй этот путь отдельным `openNavigationLink` к списку метаданных — такая
форма не имеет владельца выбора и не вернёт ссылку в табличную часть.
Если конфигурация БСП показывает пустой рабочий стол в `/TestClient`, сначала
проверь прямой `openNavigationLink`; диагностика должна показать ошибки всех
стратегий навигации. Не добавляй конфигурационный адхок. `uiaBeforeSteps`
используй только как осторожный bootstrap в скрытом desktop: на BP подтверждено,
что ввод до подключения TestManager может сделать TestClient неподключаемым.
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
IBCMD="$CODEX_IBCMD" ./scripts/build_cfe_linux.sh
```

Для платформы 8.5 можно передать точный путь к `ibcmd` или каталог версии.
Скрипт строго поддерживает оба известных Linux layout:
`<version>/ibcmd` и `<version>/bin/ibcmd`. При наличии обоих кандидатов он не
выбирает неявно и требует точный путь. Сборка использует отдельный `--data`,
проверяет ненулевой CFE и не использует Designer как запасной путь.

## Полный Linux Smoke

`linux_flow.sh` связывает реальную цепочку: `ibcmd build` → install в файловую
ИБ → изменение существующего VRD → `apache2ctl configtest` → reload Apache →
оба HTTP health-маршрута → doctor → нативный `TestClient/TestManager` в Xvfb.
Он ничего не устанавливает и явно падает при отсутствии 1С, `ibcmd`, Apache,
systemd, Python или Xvfb.

Сначала заполни перечисленные в `./scripts/linux_flow.sh --help` переменные
окружения. Для layout официальных пакетов на текущем Linux-хосте:

```bash
if [ -r /opt/1cv8/env ]; then
  . /opt/1cv8/env
fi
export CODEX_IBCMD=/opt/1cv8/x86_64/8.5.1.1529/ibcmd
export CODEX_1C_EXECUTABLE=/opt/1cv8/x86_64/8.5.1.1529/1cv8
./scripts/linux_flow.sh doctor
./scripts/linux_flow.sh run
```

`/opt/1cv8/env` является только optional environment helper: его отсутствие
не считается отсутствием платформы.

`doctor` ничего не изменяет: проверяет зависимости, Apache, оба health-маршрута
и worker config. `run` изменяет только явно указанную тестовую ИБ, её VRD,
состояние расширения и каталог артефактов; при любой ошибке останавливается.

## Основные Команды API

Все команды, кроме `health`, отправляются POST-запросом на `/command`.

- `Health` - проверка доступности
- `Metadata` - список объектов метаданных
- `Describe` - реквизиты и табличные части объекта
- `Query` - выполнение запроса 1С
- `EventLog` - чтение журнала регистрации (`ВыгрузитьЖурналРегистрации`)
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

Перед агентным запуском нового стенда выполняй `capabilities`, а при проблемах
подключения — `doctor`. Для неизвестной формы сначала используй `ui-inspect`:
его нормализованный результат компактнее сырого дерева и сразу содержит
селекторы с приоритетом `objectName > formName > title`.

Ссылки в `selectReference` задавай объектом `reference` с `kind`,
`metadataName`, `uuid`; не закрепляй представление элемента в тесте. Для
cross-db worker обязательно передай локально `targetBridgeBaseUrl` целевой базы,
поскольку `bridgeBaseUrl` относится к базе TestManager.

Сквозной сценарий «server arrange → UI act → server assert → cleanup» запускай
через `run-hybrid`. Результаты `saveAs` arrange доступны в UI и assert как
`${alias.path}`; созданные arrange-объекты удаляются автоматически. Набор
коротких независимых UI-тестов запускай через `run-ui-suite`: это одна тёплая
сессия TestClient/TestManager, и каждый сценарий должен сам закрывать формы.
Для задачи из `before` не используй `openNavigationLink`: на части
конфигураций он может потерять связь TestManager/TestClient. Открывай её через
`openForm` с `metadataKind: "task"` и UUID из `${alias.path}`. Если нужны
кнопки и поля специальной формы выполнения, используй `openTaskExecutionForm`.
