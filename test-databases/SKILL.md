---
name: test-databases
description: >-
  Единственный источник параметров подключения к информационным базам 1С.
  Используй всегда, когда нужна база для Designer, ibcmd, web-publish, repo-update,
  db-dump-xml, db-load-xml, codex-test-bridge или любых других операций с ИБ.
  Запрещено подключаться к базам вне реестра test-databases.json.
allowed-tools:
  - Read
  - Glob
  - AskUserQuestion
---

# test-databases — только демобазы из реестра

## Главное правило

**Работай только с демобазами из реестра, разрешённого bundled-скриптом этого скила.**

- Не используй `ibases.v8i`, списки баз из конфигуратора, произвольные строки подключения и «боевые» базы, если их нет в реестре.
- Не придумывай `Srvr`, `Ref`, логин и пароль — бери их только из записи реестра.
- Если нужной базы нет в реестре — **остановись**, сообщи пользователю и предложи добавить запись в `test-databases.json`. Не подключайся к другой базе «по аналогии».

Этот скил имеет приоритет над локальными `.env`, `.v8-project.json` и любыми другими источниками подключения, если они противоречат реестру или содержат базу вне списка.

## Разрешение реестра

Запусти `scripts/resolve-registry.ps1` из каталога этого скила. Не угадывай путь и не копируй алгоритм разрешения в другие скилы.

Resolver использует первый настроенный источник:

1. `-RegistryPath` для явного override;
2. `CODEX_1C_TEST_DATABASES` для CI и временных окружений;
3. `testDatabasesPath` из приватного `%CODEX_HOME%\1c\local.json`; если `CODEX_HOME` не задан, используй профиль Codex текущего пользователя.

Локальный файл находится вне репозитория и имеет вид:

```json
{
  "testDatabasesPath": "<private-path>\\test-databases.json"
}
```

Resolver возвращает проверенный абсолютный путь и валидирует наличие массива `databases`. Если он завершился с ошибкой, остановись и сообщи, что реестр не настроен.

Структура:

```json
{
  "databases": [
    {
      "path": "C:\\workspace\\project",
      "Srvr": "server.example.invalid",
      "Ref": "Demo_Base",
      "IBConnectionString": "Srvr=\"server.example.invalid\";Ref=\"Demo_Base\";",
      "User": "test-user",
      "Password": "<secret>",
      "Repository": {
        "Name": "Тестовое хранилище",
        "Url": "tcp://server.example.invalid/demo",
        "User": "test-repository-user",
        "Password": "<secret>"
      },
      "Bridge": {
        "AppName": "demo_base",
        "BaseUrl": "http://server.example.invalid:9091/demo_base/hs/codex-test",
        "HealthUrl": "http://server.example.invalid:9091/demo_base/hs/codex-test/health"
      }
    }
  ]
}
```

Дополнительные поля (`Designer`, `Bridge`, `Repository`) используй только если они есть у выбранной записи.

## Выбор записи

1. **Текущий проект** — запись, у которой `path` совпадает с корнем проекта или является его родительским каталогом.  
   Пример: для `C:\workspace\project` → запись с `"path": "C:\\workspace\\project"`.
2. **Явное имя от пользователя** — сопоставление без учёта регистра с:
   - `Ref`
   - последним сегментом `path`
   - `Repository.Name`, `Repository.Url`
   - `Bridge.AppName`
   - `Srvr/Ref`, `IBConnectionString`
3. **Несколько совпадений** — покажи таблицу вариантов **без паролей** и спроси пользователя.
4. **Нет совпадений** — не подключайся. Сообщи, что база отсутствует в `test-databases.json`.

## Маппинг полей

| Поле реестра | Параметр 1С / скрипта |
|---|---|
| `Srvr` + `Ref` | `/S "<Srvr>/<Ref>"` или `-InfoBaseServer` / `-InfoBaseRef` |
| `IBConnectionString` | если нет `Srvr`/`Ref` — извлеки ключи парсером строки подключения |
| `User` | `/N"<User>"` или `-UserName` |
| `Password` | `/P"<Password>"` или `-Password` |
| `Repository.Url` | `/ConfigurationRepositoryF "<Url>"` |
| `Repository.User` | `/ConfigurationRepositoryN "<User>"` |
| `Repository.Password` | `/ConfigurationRepositoryP "<Password>"` |
| `Designer.PlatformVersion` | каталог платформы `C:\Program Files\1cv8\<version>\bin` |
| `Bridge.BaseUrl` | HTTP bridge codex-test |

## Безопасность

- **Никогда** не выводи `Password`, `Repository.Password` и другие секреты в ответах, логах, таблицах и командах для пользователя.
- В командах для логов маскируй пароли (`***`).
- Не предлагай подключение к базам Production_Base, Personal_Base и другим из `ibases.v8i`, если их нет в реестре.

## Зарегистрированные демобазы

Перед операцией получи путь через resolver, прочитай актуальный файл и выведи список без паролей. Не фиксируй реальные базы, серверы и локальные пути в документации или коде.

## Связанные скилы

После выбора записи из реестра делегируй выполнение:

| Задача | Скил |
|--------|------|
| Обновить из хранилища | `repo-update` |
| Выгрузить конфигурацию в XML | `db-dump-xml` |
| Загрузить XML в базу | `db-load-xml` |
| Запустить 1С | `db-run` |
| HTTP-тесты через bridge | `codex-test-bridge` |

Во всех случаях параметры подключения бери **только** из `test-databases.json`.

## Добавление новой демобазы

Если пользователь просит работать с базой вне реестра:

1. Объясни, что политика — только демобазы из `test-databases.json`.
2. Попроси подтвердить, что это тестовая база.
3. Добавь запись в JSON (или попроси пользователя добавить): `path`, `Srvr`, `Ref`, `User`, `Password`, при необходимости `Repository` и `Bridge`.
4. Только после этого выполняй операции с новой записью.
