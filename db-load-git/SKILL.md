---
name: db-load-git
description: Загрузка изменений из Git в базу 1С. Используй когда пользователь просит загрузить изменения из гита, обновить базу из репозитория, partial load из коммита
allowed-tools:
  - Bash
  - Read
  - Glob
  - AskUserQuestion
---

# /db-load-git — Загрузка изменений из Git

Определяет изменённые файлы конфигурации по данным Git и выполняет частичную загрузку в информационную базу.

## Usage

```
/db-load-git [database]
/db-load-git dev                              — все незафиксированные изменения
/db-load-git dev -Source Staged               — только staged
/db-load-git dev -Source Commit -CommitRange "HEAD~3..HEAD"
/db-load-git dev -DryRun                      — только показать что будет загружено
```

## Параметры подключения

Перед обращением к ИБ обязательно примени `test-databases`: запусти `scripts/resolve-registry.ps1` из каталога этого skill и выбери разрешённую запись по его правилам. Параметры подключения, пользователя и пароль передавай только из выбранной записи.

Не принимай произвольный путь, сервер или строку подключения как замену реестру. `.v8-project.json` разрешён только для вспомогательных полей вроде `v8path`, `configSrc` или `webUrl`. Если подходящей записи нет или выбор неоднозначен, остановись и запроси уточнение.
## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/db-load-git/scripts/db-load-git.ps1 <параметры>
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
| `-ConfigDir <путь>` | да | Каталог XML-выгрузки (git-репозиторий) |
| `-Source <источник>` | нет | `All` (по умолч.) / `Staged` / `Unstaged` / `Commit` |
| `-CommitRange <range>` | для Commit | Диапазон коммитов (напр. `HEAD~3..HEAD`) |
| `-Extension <имя>` | нет | Загрузить в расширение |
| `-AllExtensions` | нет | Загрузить все расширения |
| `-Format <формат>` | нет | `Hierarchical` (по умолч.) / `Plain` |
| `-DryRun` | нет | Только показать что будет загружено (без загрузки) |
| `-UpdateDB` | нет | После загрузки сразу обновить конфигурацию БД (`/UpdateDBCfg`) |

> `*` — нужен либо `-InfoBasePath`, либо пара `-InfoBaseServer` + `-InfoBaseRef`

## После выполнения

1. Показать список загруженных файлов и результат из лога
2. Если `-UpdateDB` не был указан — **предложить `/db-update`** для применения изменений к БД

## Примеры

```powershell
# Все незафиксированные изменения
powershell.exe -NoProfile -File <skills-root>/db-load-git/scripts/db-load-git.ps1 -V8Path "C:\Program Files\1cv8\8.3.25.1257\bin" -InfoBasePath "C:\Bases\MyDB" -ConfigDir "C:\WS\cfsrc" -Source All -UpdateDB

# Из диапазона коммитов
powershell.exe -NoProfile -File <skills-root>/db-load-git/scripts/db-load-git.ps1 -InfoBasePath "C:\Bases\MyDB" -ConfigDir "C:\WS\cfsrc" -Source Commit -CommitRange "HEAD~3..HEAD"
```
