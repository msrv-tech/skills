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

Сначала используй скил `test-databases`. Скрипт `repo-update.ps1` сам вызывает его resolver; `-RegistryPath` нужен только для явного override.

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

Запускай bundled-скрипт из каталога этого скила:

```powershell
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex' }
$repoUpdateScript = Join-Path $codexRoot 'skills\repo-update\scripts\repo-update.ps1'
& $repoUpdateScript
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
