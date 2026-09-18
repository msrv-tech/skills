---
name: db-run
description: Запуск 1С:Предприятие. Используй когда пользователь просит запустить 1С, открыть базу, запустить предприятие
allowed-tools:
  - Bash
  - Read
  - Glob
  - AskUserQuestion
---

# /db-run — Запуск 1С:Предприятие

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/db-run/scripts/db-run.py" -InfoBasePath <test-infobase-path>
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/db-run/scripts/db-run.ps1" -InfoBasePath <test-infobase-path>
```
<!-- docs-evals:python-entrypoint:end -->

Запускает информационную базу в режиме 1С:Предприятие (пользовательский режим).

## Usage

```
/db-run [database]
/db-run dev
/db-run dev /Execute process.epf
/db-run dev /C "параметр запуска"
```

## Параметры подключения

Перед обращением к ИБ обязательно примени `test-databases`: на Linux запусти `python3 <skills-root>/test-databases/scripts/resolve-registry.py`, а на Windows — `resolve-registry.ps1` через PowerShell; затем выбери разрешённую запись по его правилам. Параметры подключения, пользователя и пароль передавай только из выбранной записи.

Не принимай произвольный путь, сервер или строку подключения как замену реестру. `.v8-project.json` разрешён только для вспомогательных полей вроде `v8path`, `configSrc` или `webUrl`. Если подходящей записи нет или выбор неоднозначен, остановись и запроси уточнение.
## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/db-run/scripts/db-run.ps1 <параметры>
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
| `-Execute <файл.epf>` | нет | Запуск внешней обработки сразу после старта |
| `-CParam <строка>` | нет | Параметр запуска (/C) |
| `-URL <ссылка>` | нет | Навигационная ссылка (формат `e1cib/...`) |

> `*` — нужен либо `-InfoBasePath`, либо пара `-InfoBaseServer` + `-InfoBaseRef`

## Важно

Скрипт запускает 1С в фоне (`Start-Process` без `-Wait`) — управление возвращается сразу.

## Примеры

```powershell
# Простой запуск
powershell.exe -NoProfile -File <skills-root>/db-run/scripts/db-run.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin"

# Запуск с обработкой
powershell.exe -NoProfile -File <skills-root>/db-run/scripts/db-run.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -Execute "C:\epf\МояОбработка.epf"

# Открыть по навигационной ссылке
powershell.exe -NoProfile -File <skills-root>/db-run/scripts/db-run.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -URL "e1cib/data/Справочник.Номенклатура"

# Серверная база с параметром запуска
powershell.exe -NoProfile -File <skills-root>/db-run/scripts/db-run.ps1 -InfoBaseServer "srv01" -InfoBaseRef "MyDB" -UserName "Admin" -Password "secret" -CParam "ЗапуститьОбновление"
```
