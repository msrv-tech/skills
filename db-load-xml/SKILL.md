---
name: db-load-xml
description: Загрузка конфигурации 1С из XML-файлов. Используй когда пользователь просит загрузить конфигурацию из файлов, XML, исходников, LoadConfigFromFiles
allowed-tools:
  - Bash
  - Read
  - Glob
  - AskUserQuestion
---

# /db-load-xml — Загрузка конфигурации из XML

Загружает конфигурацию в информационную базу из XML-файлов (исходников). Поддерживает полную и частичную загрузку.

> **EDT MCP**: Если проект открыт в EDT и доступен EDT MCP-сервер - этот скил не нужен. EDT работает напрямую с XML-исходниками, а для обновления БД используй `update_database` через MCP. Используй этот скил только если пользователь явно просит загрузку через конфигуратор.

## Usage

```
/db-load-xml <configDir> [database]
/db-load-xml src/config dev
/db-load-xml src/config dev -Mode Partial -Files "Catalogs/Номенклатура.xml,Catalogs/Номенклатура/Ext/ObjectModule.bsl"
```

> **Внимание**: полная загрузка **заменяет всю конфигурацию** в базе. Перед выполнением запроси подтверждение у пользователя.

## Параметры подключения

Перед обращением к ИБ обязательно примени `test-databases`: запусти `scripts/resolve-registry.ps1` из каталога этого skill и выбери разрешённую запись по его правилам. Параметры подключения, пользователя и пароль передавай только из выбранной записи.

Не принимай произвольный путь, сервер или строку подключения как замену реестру. `.v8-project.json` разрешён только для вспомогательных полей вроде `v8path`, `configSrc` или `webUrl`. Если подходящей записи нет или выбор неоднозначен, остановись и запроси уточнение.
## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/db-load-xml/scripts/db-load-xml.ps1 <параметры>
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
| `-ConfigDir <путь>` | да | Каталог XML-исходников |
| `-Mode <режим>` | нет | `Full` (по умолч.) / `Partial` |
| `-Files <список>` | для Partial | Относительные пути файлов через запятую |
| `-ListFile <путь>` | для Partial | Путь к файлу со списком (альтернатива `-Files`) |
| `-Extension <имя>` | нет | Загрузить в расширение |
| `-AllExtensions` | нет | Загрузить все расширения |
| `-Format <формат>` | нет | `Hierarchical` (по умолч.) / `Plain` |
| `-UpdateDB` | нет | После загрузки сразу обновить конфигурацию БД (`/UpdateDBCfg`) |

> `*` — нужен либо `-InfoBasePath`, либо пара `-InfoBaseServer` + `-InfoBaseRef`

### Режимы загрузки

| Режим | Описание |
|-------|----------|
| `Full` | Полная загрузка — замена всей конфигурации из каталога XML |
| `Partial` | Частичная — загрузка выбранных файлов (с `-partial -updateConfigDumpInfo`) |

### Формат файла списка (listFile)

Файл содержит **относительные пути к файлам** в каталоге выгрузки (один на строку), кодировка **UTF-8 с BOM**:

```
Catalogs/Номенклатура.xml
Catalogs/Номенклатура/Ext/ObjectModule.bsl
Documents/Заказ.xml
Documents/Заказ/Forms/ФормаДокумента.xml
```

## Коды возврата

| Код | Описание |
|-----|----------|
| 0 | Успешно |
| 1 | Ошибка (см. лог) |

## После выполнения

1. Прочитай лог и покажи результат
2. Если `-UpdateDB` не был указан — **предложи выполнить `/db-update`** для применения изменений к БД

## Примеры

```powershell
# Полная загрузка
powershell.exe -NoProfile -File <skills-root>/db-load-xml/scripts/db-load-xml.ps1 -V8Path "C:\Program Files\1cv8\8.3.25.1257\bin" -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -ConfigDir "C:\WS\cfsrc" -Mode Full

# Частичная загрузка конкретных файлов
powershell.exe -NoProfile -File <skills-root>/db-load-xml/scripts/db-load-xml.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -ConfigDir "C:\WS\cfsrc" -Mode Partial -Files "Catalogs/Номенклатура.xml,Catalogs/Номенклатура/Ext/ObjectModule.bsl"

# Загрузка расширения
powershell.exe -NoProfile -File <skills-root>/db-load-xml/scripts/db-load-xml.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -ConfigDir "C:\WS\ext_src" -Mode Full -Extension "МоёРасширение"

# Загрузка + обновление БД в одном запуске
powershell.exe -NoProfile -File <skills-root>/db-load-xml/scripts/db-load-xml.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin" -ConfigDir "C:\WS\cfsrc" -Mode Full -UpdateDB
```
