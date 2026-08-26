---
name: db-load-cf
description: Загрузка конфигурации 1С из CF-файла. Используй когда пользователь просит загрузить конфигурацию из CF, восстановить из бэкапа CF
allowed-tools:
  - Bash
  - Read
  - Glob
  - AskUserQuestion
---

# /db-load-cf — Загрузка конфигурации из CF-файла

Загружает конфигурацию из бинарного CF-файла в информационную базу.

## Usage

```
/db-load-cf <input.cf> [database]
/db-load-cf config.cf dev
```

> **Внимание**: загрузка CF **полностью заменяет** конфигурацию в базе. Перед выполнением запроси подтверждение у пользователя.

## Параметры подключения

Перед обращением к ИБ обязательно примени `test-databases`: запусти `scripts/resolve-registry.ps1` из каталога этого skill и выбери разрешённую запись по его правилам. Параметры подключения, пользователя и пароль передавай только из выбранной записи.

Не принимай произвольный путь, сервер или строку подключения как замену реестру. `.v8-project.json` разрешён только для вспомогательных полей вроде `v8path`, `configSrc` или `webUrl`. Если подходящей записи нет или выбор неоднозначен, остановись и запроси уточнение.
## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/db-load-cf/scripts/db-load-cf.ps1 <параметры>
```

### Параметры скрипта

| Параметр | Обязательный | Описание |
|----------|:------------:|----------|
| `-V8Path <путь>` | нет | Каталог bin платформы (или полный путь к 1cv8.exe) |
| `-InfoBasePath <путь>` | * | Файловая база |
| `-InfoBaseServer <сервер>` | * | Сервер 1С (для серверной базы) |
| `-InfoBaseRef <имя>` | * | Имя базы на сервере |
| `-UserName <имя>` | нет | Имя пользователя |
| `-Password <пароль>` | нет | Пароль |
| `-InputFile <путь>` | да | Путь к CF-файлу |
| `-Extension <имя>` | нет | Загрузить как расширение |
| `-AllExtensions` | нет | Загрузить все расширения из архива |

> `*` — нужен либо `-InfoBasePath`, либо пара `-InfoBaseServer` + `-InfoBaseRef`

## Коды возврата

| Код | Описание |
|-----|----------|
| 0 | Успешно |
| 1 | Ошибка (см. лог) |

## После выполнения

1. Прочитай лог-файл и покажи результат
2. **Предложи выполнить `/db-update`** — загрузка CF обновляет только «основную» конфигурацию конфигуратора, для применения к БД нужен `/UpdateDBCfg`

## Примеры

```powershell
# Файловая база
powershell.exe -NoProfile -File <skills-root>/db-load-cf/scripts/db-load-cf.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -InputFile "C:\backup\config.cf"

# Серверная база
powershell.exe -NoProfile -File <skills-root>/db-load-cf/scripts/db-load-cf.ps1 -InfoBaseServer "srv01" -InfoBaseRef "MyApp_Test" -UserName "Admin" -Password "secret" -InputFile "config.cf"

# Загрузка расширения
powershell.exe -NoProfile -File <skills-root>/db-load-cf/scripts/db-load-cf.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -InputFile "ext.cfe" -Extension "МоёРасширение"
```
