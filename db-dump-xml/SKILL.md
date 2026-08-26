---
name: db-dump-xml
description: Выгрузка конфигурации 1С в XML-файлы. Используй когда пользователь просит выгрузить конфигурацию в файлы, XML, исходники, DumpConfigToFiles
allowed-tools:
  - Bash
  - Read
  - Glob
  - AskUserQuestion
---

# /db-dump-xml — Выгрузка конфигурации в XML

Выгружает конфигурацию информационной базы в XML-файлы (исходники). Поддерживает полную, инкрементальную, частичную выгрузку и обновление ConfigDumpInfo.

> **EDT MCP**: Если проект открыт в EDT и доступен EDT MCP-сервер - этот скил не нужен. EDT работает напрямую с XML-исходниками, выгрузка из БД не требуется. Используй этот скил только если пользователь явно просит выгрузку через конфигуратор.

## Usage

```
/db-dump-xml [database] [outputDir]
/db-dump-xml dev src/config
/db-dump-xml dev src/config -Mode Full
/db-dump-xml dev src/config -Mode Partial -Objects "Справочник.Номенклатура,Документ.Заказ"
```

## Параметры подключения

Перед обращением к ИБ обязательно примени `test-databases`: запусти `scripts/resolve-registry.ps1` из каталога этого skill и выбери разрешённую запись по его правилам. Параметры подключения, пользователя и пароль передавай только из выбранной записи.

Не принимай произвольный путь, сервер или строку подключения как замену реестру. `.v8-project.json` разрешён только для вспомогательных полей вроде `v8path`, `configSrc` или `webUrl`. Если подходящей записи нет или выбор неоднозначен, остановись и запроси уточнение.
## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/db-dump-xml/scripts/db-dump-xml.ps1 <параметры>
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
| `-ConfigDir <путь>` | да | Каталог для выгрузки |
| `-Mode <режим>` | нет | `Full` / `Changes` (по умолч.) / `Partial` / `UpdateInfo` |
| `-Objects <список>` | для Partial | Имена объектов через запятую |
| `-Extension <имя>` | нет | Выгрузить расширение |
| `-AllExtensions` | нет | Выгрузить все расширения |
| `-Format <формат>` | нет | `Hierarchical` (по умолч.) / `Plain` |

> `*` — нужен либо `-InfoBasePath`, либо пара `-InfoBaseServer` + `-InfoBaseRef`

### Режимы выгрузки

| Режим | Описание |
|-------|----------|
| `Full` | Полная выгрузка — все объекты конфигурации |
| `Changes` | Инкрементальная — только изменённые с последней выгрузки (использует ConfigDumpInfo.xml) |
| `Partial` | Частичная — выбранные объекты из параметра `-Objects` |
| `UpdateInfo` | Обновить только ConfigDumpInfo.xml без выгрузки файлов |

## Коды возврата

| Код | Описание |
|-----|----------|
| 0 | Успешно |
| 1 | Ошибка (см. лог) |

> Если пользователь просит выгрузить конкретные объекты — используй `-Mode Partial` с `-Objects`.

## Примеры

```powershell
# Полная выгрузка (файловая база)
powershell.exe -NoProfile -File <skills-root>/db-dump-xml/scripts/db-dump-xml.ps1 -V8Path "C:\Program Files\1cv8\8.3.25.1257\bin" -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -ConfigDir "C:\WS\cfsrc" -Mode Full

# Инкрементальная выгрузка
powershell.exe -NoProfile -File <skills-root>/db-dump-xml/scripts/db-dump-xml.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -ConfigDir "C:\WS\cfsrc" -Mode Changes

# Частичная выгрузка
powershell.exe -NoProfile -File <skills-root>/db-dump-xml/scripts/db-dump-xml.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -ConfigDir "C:\WS\cfsrc" -Mode Partial -Objects "Справочник.Номенклатура,Документ.Заказ"

# Серверная база
powershell.exe -NoProfile -File <skills-root>/db-dump-xml/scripts/db-dump-xml.ps1 -InfoBaseServer "srv01" -InfoBaseRef "MyApp_Dev" -UserName "Admin" -Password "secret" -ConfigDir "C:\WS\cfsrc" -Mode Full

# Выгрузка расширения
powershell.exe -NoProfile -File <skills-root>/db-dump-xml/scripts/db-dump-xml.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -ConfigDir "C:\WS\ext_src" -Mode Full -Extension "МоёРасширение"
```
