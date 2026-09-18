---
name: repo-update
description: Обновление конфигурации 1С из хранилища конфигурации. Используй, когда пользователь просит получить изменения из хранилища, обновить конфигурацию из хранилища, выполнить ConfigurationRepositoryUpdateCfg, подтянуть последнюю версию хранилища 1С.
allowed-tools:
  - Bash
  - Read
  - Glob
  - AskUserQuestion
---

# /repo-update - Обновление из хранилища 1С

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/repo-update/scripts/repo-update.py" -RegistryPath <private-registry.json> -Database <registered-test-database>
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/repo-update/scripts/repo-update.ps1" -RegistryPath <private-registry.json> -Database <registered-test-database>
```
<!-- docs-evals:python-entrypoint:end -->

Получает конфигурацию из хранилища 1С в локальную конфигурацию выбранной информационной базы через пакетный режим конфигуратора:
`/ConfigurationRepositoryUpdateCfg`.

Этот скил делает только получение из хранилища. Не помещай изменения, не захватывай и не освобождай объекты этим скилом.

## Usage

```powershell
/repo-update
/repo-update zup
/repo-update bp -Force
/repo-update erp -Revised -UpdateDB
/repo-update zup -Version 123
```

## Источник параметров

Сначала используй скил `test-databases`. Python- и PowerShell-скрипты вызывают
общий resolver; `-RegistryPath` нужен только для явного override.

Правила выбора записи:
1. Если пользователь указал базу, сопоставь ее с `Ref`, последним сегментом `path`, `Repository.Name`, `Repository.Url`, `Srvr/Ref`.
2. Если пользователь не указал базу, выбери запись, у которой `path` совпадает с текущим проектом или является его ближайшим родительским каталогом.
3. Если найдено несколько записей, покажи варианты без паролей и спроси пользователя.
4. Если у записи нет `Repository`, сообщи, что для этой базы хранилище не задано в `test-databases.json`.

Ожидаемые поля:

```json
{
  "path": "C:\\workspace\\project",
  "Srvr": "server.example.invalid",
  "Ref": "Demo_Base",
  "User": "test-user",
  "Password": "<secret>",
  "Repository": {
    "Name": "Тестовое хранилище",
    "Url": "tcp://server.example.invalid/demo",
    "User": "test-repository-user",
    "Password": "<secret>"
  }
}
```

Никогда не выводи пароли из `Password` и `Repository.Password` в ответах, таблицах и логах.

## Команда

Linux — основной backend. Путь к `1cv8` можно передать через `-V8Path`, задать
в `ONEC_1CV8_PATH`/`CODEX_1C_EXECUTABLE` или разрешить строго из
`/opt/1cv8/x86_64/<version>/1cv8` либо
`/opt/1cv8/x86_64/<version>/bin/1cv8`:

```bash
python3 <skills-root>/repo-update/scripts/repo-update.py \
  -ProjectPath <project-root>
python3 <skills-root>/repo-update/scripts/repo-update.py \
  -Database <registered-test-database> -Force -UpdateDB
```

Windows PowerShell — отдельный вариант:

```powershell
powershell.exe -NoProfile -File <skills-root>/repo-update/scripts/repo-update.ps1 `
  -ProjectPath <project-root>
```

### Параметры скрипта

| Параметр | Описание |
|---|---|
| `-Database <name>` | Явное имя базы: `zup`, `bp`, `erp`, `Demo_Base`, часть URL хранилища |
| `-ProjectPath <path>` | Путь проекта для автоопределения, по умолчанию текущий каталог |
| `-RegistryPath <path>` | Явный override JSON-реестра; без параметра путь разрешается скилом `test-databases` |
| `-V8Path <path>` | Каталог `bin` платформы или полный путь к `1cv8.exe` |
| `-Version <number>` | Версия хранилища для `-v`; без параметра берется последняя |
| `-Revised` | Передать `-revised`, перезаписывая локальные изменения по объектам |
| `-Force` | Передать `-force`, подтверждая добавление/удаление объектов |
| `-Objects <file>` | XML-файл списка объектов для частичного обновления |
| `-Extension <name>` | Обновить хранилище расширения |
| `-UpdateDB` | После получения из хранилища выполнить `/UpdateDBCfg` |
| `-DryRun` | Показать выбранную базу и команду без запуска 1С |

## Безопасность

- Перед `-Revised` предупреждай пользователя: параметр может перезаписать локальные изменения.
- Перед `-UpdateDB` помни, что это уже применение конфигурации к БД; если изменения значительные, может потребоваться монопольный доступ.
- Если пользователь просит "обновить из хранилища и применить", используй `-UpdateDB`; иначе только получи конфигурацию из хранилища.
- В выводе скрипта команда печатается с замаскированными паролями.

## Примеры

Linux:

```bash
# Текущий проект
python3 <skills-root>/repo-update/scripts/repo-update.py \
  -ProjectPath <project-root>

# Явно выбранная тестовая база
python3 <skills-root>/repo-update/scripts/repo-update.py \
  -Database demo -Force

# Получить и применить к БД
python3 <skills-root>/repo-update/scripts/repo-update.py \
  -Database demo -Force -UpdateDB
```

Windows:

```powershell
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex' }
$repoUpdateScript = Join-Path $codexRoot 'skills\repo-update\scripts\repo-update.ps1'

# Текущий проект
& $repoUpdateScript

# Явно выбранная тестовая база
& $repoUpdateScript -Database demo -Force

# Получить и применить к БД
& $repoUpdateScript -Database demo -Force -UpdateDB
```
