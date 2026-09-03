# Codex Test Bridge

Поставляются две сборки:

- `codex-test-bridge.cfe` — HTTP API и нативный UI-worker для режима
  совместимости `8.3.12+`;
- `codex-test-bridge-legacy.cfe` — тот же server-side HTTP API без `uiJob*` и
  UI-метаданных для режимов `8.3.11` и ниже. UI таких баз тестируется через
  отдельную ИБ-менеджер с полной сборкой.

Режим основной конфигурации ради bridge не повышается.
Full-сборка не переопределяет `DefaultRoles` и использует права пользователя
тестовой ИБ — это позволяет UI-worker работать в конфигурациях `8.3.12–8.3.13`.

Служебное расширение для демо/тестовых баз. Публикует HTTP-сервис `codex-test`
и дает внешний JSON API для быстрых проверок с Linux-агента.

Это расширение намеренно рассчитано на доверенные демо-базы. Оно выполняет
команды с привилегиями серверного кода 1С, поэтому не подключайте его к боевым
базам и не публикуйте наружу.

## Endpoints

После подключения расширения и публикации базы HTTP-сервис доступен как:

```text
http://<host>/<publication>/hs/codex-test/health
http://<host>/<publication>/hs/codex-test/command
```

Для HTTP-сервисов из расширений в `default.vrd` должна быть разрешена публикация
расширений:

```xml
<httpServices publishByDefault="true" publishExtensionsByDefault="true">
  <service name="CodexTestBridge" rootUrl="codex-test" enable="true"
           reuseSessions="dontuse" sessionMaxAge="20"/>
</httpServices>
```

## Commands

Все команды отправляются `POST /hs/codex-test/command` JSON-телом.

Расширение не завязано на УНФ: все универсальные команды принимают `kind`
(`catalog`, `document`, `enum`) и имя объекта метаданных.

### Health

```json
{"command":"Health"}
```

### Metadata

```json
{
  "command": "Metadata",
  "sections": ["catalogs", "documents", "enums"]
}
```

`sections` можно не передавать, тогда вернутся основные коллекции метаданных.

### Describe

```json
{
  "command": "Describe",
  "kind": "catalog",
  "name": "Контрагенты"
}
```

Возвращает реквизиты и табличные части объекта метаданных.

### Query

```json
{
  "command": "Query",
  "text": "ВЫБРАТЬ ПЕРВЫЕ 10 Ссылка, Наименование ИЗ Справочник.Контрагенты",
  "limit": 10,
  "params": {}
}
```

### ExecuteBSL

Выполняет серверный код через `Выполнить()`. В коде доступен массив
`Параметры`; чтобы вернуть значение, запишите его в `РезультатВыполнения`.

```json
{
  "command": "ExecuteBSL",
  "code": "РезультатВыполнения = ТекущаяДата();",
  "params": []
}
```

### CallCommonModule

Вызывает экспортную функцию или процедуру общего модуля. `params` передаются как
позиционные аргументы. Для процедуры передайте `expectResult: false`.

```json
{
  "command": "CallCommonModule",
  "module": "ОбщегоНазначения",
  "method": "ЗначениеРеквизитаОбъекта",
  "params": [
    {"type": "CatalogRef", "name": "Контрагенты", "uuid": "00000000-0000-0000-0000-000000000000"},
    "Наименование"
  ],
  "expectResult": true
}
```

### WriteObject

Создает или обновляет объект данных. Если `uuid` не передан, объект создается.

```json
{
  "command": "WriteObject",
  "kind": "catalog",
  "name": "Контрагенты",
  "fields": {
    "Наименование": "Codex test customer"
  }
}
```

Для документа:

```json
{
  "command": "WriteObject",
  "kind": "document",
  "name": "ЗаказПокупателя",
  "fields": {
    "Дата": {"type": "Date", "value": "20260521100000"}
  },
  "tables": {},
  "writeMode": "write"
}
```

`writeMode` может быть `write` или `post`. `post` применяется только к
документам.

### GetObject

```json
{
  "command": "GetObject",
  "kind": "catalog",
  "name": "Контрагенты",
  "uuid": "00000000-0000-0000-0000-000000000000",
  "includeTables": true
}
```

### DeleteObject

Устанавливает или снимает пометку удаления.

```json
{
  "command": "DeleteObject",
  "kind": "catalog",
  "name": "Контрагенты",
  "uuid": "00000000-0000-0000-0000-000000000000",
  "deletionMark": true
}
```

### Compatibility commands

Старые команды оставлены как обертки над универсальным API:

- `CreateCatalogItem`
- `CreateDocument`
- `PostDocument`

### RenderExternalPrintForm

Серверная проверка внешней печатной формы без UI. Команда создает внешнюю
обработку из `externalPath`, берет документ по `uuid` либо первый документ
указанного вида, вызывает экспортную процедуру/функцию
`СформироватьПечатнуюФормуДляТеста(МассивОбъектов)` и сохраняет результат в
`mxl`, `html`, `txt`.

```json
{
  "command": "RenderExternalPrintForm",
  "externalPath": "<server-visible-epf-path>",
  "outputDir": "<server-visible-output-directory>",
  "outputName": "print-result",
  "assignment": "Документ.ЗаказПокупателя",
  "documentName": "ЗаказПокупателя",
  "uuid": ""
}
```

`assignment` нужен для обычных ВПФ, `documentName` можно передать явно. Агент
разработки должен добавлять в ВПФ экспортную функцию
`СформироватьПечатнуюФормуДляТеста`, чтобы pipeline мог получить
машиночитаемый результат и проверить текст, дубли заголовков, границы таблиц и
итоги.

### RenderExternalReport

Серверная проверка внешнего отчета без UI. Команда создает внешний отчет из
`externalPath`, вызывает экспортную функцию
`СформироватьОтчетДляТеста(Параметры)` и сохраняет возвращенный
`ТабличныйДокумент` в `mxl`, `html`, `txt`.

```json
{
  "command": "RenderExternalReport",
  "externalPath": "<server-visible-erf-path>",
  "outputDir": "<server-visible-output-directory>",
  "outputName": "report-result",
  "reportParams": {}
}
```

Агент разработки должен добавлять в ERF экспортную функцию
`СформироватьОтчетДляТеста`, чтобы pipeline мог получить машиночитаемый
результат отчета и проверить пользовательские тексты, таблицы и итоги.

### Ref values

Для ссылочных значений можно передать UUID ссылки:

```json
{
  "type": "CatalogRef",
  "name": "Контрагенты",
  "uuid": "00000000-0000-0000-0000-000000000000"
}
```

Поддерживаются `CatalogRef`, `DocumentRef`, `EnumRef`.

Также можно использовать универсальный формат:

```json
{
  "kind": "catalog",
  "name": "Контрагенты",
  "uuid": "00000000-0000-0000-0000-000000000000"
}
```

## Python client

Клиент принудительно отключает proxy, потому что на dev-машине задан
`HTTP_PROXY`, а локальные обращения к `127.0.0.1` иначе уходят через proxy и
возвращают ложный `502`.

```bash
$bridgeUrl = $env:CODEX_1C_BRIDGE_URL
python .\client.py --base-url $bridgeUrl health
python .\client.py --base-url $bridgeUrl metadata --sections catalogs,documents
python .\client.py --base-url $bridgeUrl describe catalog Контрагенты
python .\client.py --base-url $bridgeUrl write-object catalog Контрагенты --fields "{`"Наименование`":`"Codex smoke`"}"
python .\client.py --base-url $bridgeUrl render-print-form $env:CODEX_1C_EPF_PATH --output-dir $env:CODEX_1C_OUTPUT_DIR --assignment Документ.ЗаказПокупателя --document-name ЗаказПокупателя
python .\client.py --base-url $bridgeUrl render-report $env:CODEX_1C_ERF_PATH --output-dir $env:CODEX_1C_OUTPUT_DIR
```

## Headless-сценарии для ИИ-агентов

`scenario_runner.py` выполняет декларативный JSON-сценарий поверх HTTP API.
Сценарий не запускает клиент 1С и не открывает окна. Поддерживаются:

- последовательные вызовы любых команд bridge;
- сохранение ответа шага через `saveAs`;
- подстановка `${alias.path}` в следующих шагах;
- проверки `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains`, `matches`,
  `exists`, `empty`, `notEmpty`;
- повтор шага до выполнения проверки;
- автоматическая пометка на удаление созданных справочников и документов;
- единый JSON-отчет с `runId`, длительностью, запросами и ответами.

Файл [`scenario.schema.json`](scenario.schema.json) содержит JSON Schema Draft
2020-12. Укажи `"$schema": "../scenario.schema.json"` в сценарии, чтобы IDE и
ИИ-инструменты получали автодополнение и проверку структуры. CLI дополнительно
валидирует обязательные поля, aliases, retry и операторы assertions без внешних
Python-зависимостей.

Запуск smoke-примера:

```powershell
python .\client.py `
  --base-url $env:CODEX_1C_BRIDGE_URL `
  run-scenario .\examples\smoke.scenario.json `
  --report .\artifacts\smoke-report.json
```

Набор сценариев запускается рекурсивно по маске `*.scenario.json`. Отчёты
рекомендуется писать в отдельный каталог `artifacts`, поэтому они никогда не
попадут в следующий прогон:

```powershell
python .\client.py `
  --base-url $env:CODEX_1C_BRIDGE_URL `
  run-suite .\examples `
  --report .\artifacts\suite.json `
  --junit .\artifacts\junit.xml
```

Опция `--fail-fast` останавливает suite после первого упавшего или невалидного
сценария. Без неё каждый сценарий выполняет собственный cleanup и остальные
тесты продолжаются.

Формат шага:

```json
{
  "name": "Дождаться движения документа",
  "saveAs": "movements",
  "request": {
    "command": "Query",
    "text": "ВЫБРАТЬ ... ГДЕ Документ = &Документ",
    "params": {"Документ": "${document.ref}"}
  },
  "retry": {"attempts": 10, "delaySeconds": 1},
  "assert": [
    {"path": "count", "operator": "gte", "expected": 1}
  ]
}
```

Cleanup включен по умолчанию. Его можно отключить на уровне сценария полем
`"cleanup": false`. Cleanup выполняется и при падении шага, но является
компенсирующей операцией: объекты получают пометку удаления, а не удаляются
физически.

Для побочных эффектов, которые нельзя определить по `WriteObject`, добавь
явные команды `finally`. Они всегда выполняются в обратном порядке:

```json
{
  "steps": [
    {"saveAs": "setting", "request": {"command": "CallCommonModule", "module": "Тесты", "method": "ВключитьРежим"}}
  ],
  "finally": [
    {"request": {"command": "CallCommonModule", "module": "Тесты", "method": "ВыключитьРежим"}}
  ]
}
```

Если cleanup падает после успешных шагов, прогон получает
`status: "cleanupFailed"` и ненулевой код возврата. Секретные поля запроса можно
исключить из отчета через `redactRequest`:

```json
{
  "request": {"command": "WriteObject", "fields": {"Password": "secret"}},
  "redactRequest": ["fields.Password"]
}
```

Транспортный таймаут задается общей опцией `--timeout`. HTTP-ошибки bridge
возвращаются в отчет с полем `httpStatus` и участвуют в обычном механизме retry.

## Изолированные нативные UI-тесты

Для сценариев, которые действительно должны проверить управляемую форму,
используй `run-ui`. Worker запускает штатные `/TestClient` и `/TestManager` на
невидимом Windows desktop или в Xvfb и не требует web-клиента:

```powershell
python .\client.py run-ui `
  .\server.example.invalid.json `
  .\examples\native-ui-smoke.ui.json `
  --artifact-dir .\artifacts\ui-smoke `
  --report .\artifacts\ui-smoke\worker.json
```

Примеры настроек — `ui-worker.example.json`, шаблон серверной ИБ
`ui-worker.server.example.json` и cross-database шаблон
`ui-worker.cross-db.example.json`. Для конфигураций с прикладным списком
пользователей есть `ui-worker.cross-db.credentials.example.json`. Все используют
только env-плейсхолдеры. Worker автоматически добавляет
`/DisableStartupDialogs /DisableStartupMessages /DisableSplash`; TestManager
закрывает только безопасные стартовые диалоги.
Автоматический выбор `Перезапустить` по умолчанию отключён; при необходимости
он включается в сценарии через `restartTestClientOnStartup: true`.
Встроенный test manager находится в модуле
управляемого приложения CFE; внешние обработки не нужны. Полный контракт backend,
DSL и placeholders описан в [`UI_WORKER.md`](UI_WORKER.md).
Сценарий и результат передаются через команды `uiJobCreate`, `uiJobGet` и
`uiJobDelete` и хранятся в регистре расширения `CodexUIJobs`. Поэтому встроенный
TestManager совместим с безопасным режимом CFE и не требует доступа к файлам.
`process` предназначен только для диагностики; на Windows применяй
`windowsDesktop` или `auto`, чтобы окна 1С не появлялись на рабочем столе.
Доступы из `test-databases.json` в Windows PowerShell читай только с
`Get-Content -Encoding UTF8`, иначе кириллический логин будет искажён до
передачи в TestClient.

В конфигурациях с режимом `8.3.11` и ниже платформа не разрешает внедрить
перехват модуля управляемого приложения. В этом случае целевая база запускается
как обычный `/TestClient`, а `/TestManager` — в отдельной тестовой базе с полным
bridge. Тестовый протокол 1С не требует совпадения конфигураций этих баз.
`scripts/run_cross_db_ui_with_bootstrap.py` может создать в обеих тестовых ИБ
скрытых одноразовых пользователей без пароля, выполнить сценарий и удалить их в
`finally`; запуск требует явного `--allow-bootstrap-user`.
Если конфигурация не регистрирует платформенного пользователя в прикладном
списке БСП, используй credentials-шаблон и существующего прикладного тестового
пользователя: диалог с единственной кнопкой завершения сеанса не является
устранимой заставкой.

## Build

Пример сборки CFE из XML на Linux:

```bash
P=/opt/1cv8/x86_64/8.3.27.1859
WORK=/tmp/codex-test-bridge-build
rm -rf "$WORK"
mkdir -p "$WORK"
$P/ibcmd infobase create --database-path "$WORK/ib"
$P/ibcmd extension --database-path "$WORK/ib" create \
  --name=CodexTestBridge --name-prefix=CTB --purpose=add-on
$P/ibcmd config import --database-path "$WORK/ib" \
  --extension=CodexTestBridge ./src
$P/ibcmd config check --database-path "$WORK/ib" \
  --extension=CodexTestBridge --force
$P/ibcmd config save --database-path "$WORK/ib" \
  --extension=CodexTestBridge ./codex-test-bridge.cfe
```

## Контракт для агентов

Перед генерацией теста агент может проверить установленный вариант bridge:

```powershell
python .\client.py --base-url $bridgeUrl capabilities
python .\client.py --base-url $bridgeUrl doctor --worker-config .\local.worker.json
```

`capabilities` сообщает версию контракта, `full|legacy`, серверные команды и
доступность UI worker. `doctor` не запускает 1С: он проверяет HTTP-контракт и
валидность локальной конфигурации worker.

Для сквозного теста используй `run-hybrid`: server arrange создаёт данные,
результаты `saveAs` подставляются в UI-сценарий, затем выполняется server assert,
а созданные arrange-объекты удаляются даже при падении UI:

```powershell
python .\client.py --base-url $bridgeUrl run-hybrid .\local.worker.json .\case.hybrid.json --artifact-dir .\artifacts\case
```

Несколько коротких UI-сценариев можно выполнить одним запуском клиента и
менеджера: `run-ui-batch worker.json a.ui.json b.ui.json`. Это тёплый batch, а
не фоновый сервис: процессы гарантированно завершаются после набора.
