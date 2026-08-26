---
name: db-dump-cf
description: Выгрузка конфигурации 1С в CF-файл. Используй когда пользователь просит выгрузить конфигурацию в CF, сохранить конфигурацию, сделать бэкап CF
allowed-tools:
  - Bash
  - Read
  - Glob
  - AskUserQuestion
---

# /db-dump-cf — Выгрузка конфигурации в CF-файл

Выгружает конфигурацию информационной базы в бинарный CF-файл.

## Usage

```
/db-dump-cf [database] [output.cf]
/db-dump-cf dev config.cf
/db-dump-cf                          — база по умолчанию, файл config.cf
```

## Параметры подключения

Перед обращением к ИБ обязательно примени `test-databases`: запусти `scripts/resolve-registry.ps1` из каталога этого skill и выбери разрешённую запись по его правилам. Параметры подключения, пользователя и пароль передавай только из выбранной записи.

Не принимай произвольный путь, сервер или строку подключения как замену реестру. `.v8-project.json` разрешён только для вспомогательных полей вроде `v8path`, `configSrc` или `webUrl`. Если подходящей записи нет или выбор неоднозначен, остановись и запроси уточнение.
## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/db-dump-cf/scripts/db-dump-cf.ps1 <параметры>
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
| `-OutputFile <путь>` | да | Путь к выходному CF-файлу |
| `-Extension <имя>` | нет | Выгрузить расширение |
| `-AllExtensions` | нет | Выгрузить все расширения |

> `*` — нужен либо `-InfoBasePath`, либо пара `-InfoBaseServer` + `-InfoBaseRef`

## Коды возврата

| Код | Описание |
|-----|----------|
| 0 | Успешно |
| 1 | Ошибка (см. лог) |

## После выполнения

Прочитай лог-файл и покажи результат. Если есть ошибки — покажи содержимое лога.

## Примеры

```powershell
# Выгрузка конфигурации (файловая база)
powershell.exe -NoProfile -File <skills-root>/db-dump-cf/scripts/db-dump-cf.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -OutputFile "C:\backup\config.cf"

# Серверная база
powershell.exe -NoProfile -File <skills-root>/db-dump-cf/scripts/db-dump-cf.ps1 -InfoBaseServer "srv01" -InfoBaseRef "MyApp_Dev" -UserName "Admin" -Password "secret" -OutputFile "config.cf"

# Выгрузка расширения
powershell.exe -NoProfile -File <skills-root>/db-dump-cf/scripts/db-dump-cf.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -OutputFile "ext.cfe" -Extension "МоёРасширение"
```
