---
name: epf-dump
description: Разобрать EPF-файл обработки 1С (EPF/ERF) в XML-исходники. Используй когда пользователь просит разобрать, декомпилировать обработку, получить исходники из EPF/ERF файла
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
---

# /epf-dump — Разборка обработки

## Usage

```
/epf-dump <EpfFile> [OutDir]
```

| Параметр | Обязательный | По умолчанию | Описание                            |
|----------|:------------:|--------------|-------------------------------------|
| EpfFile  | да           | —            | Путь к EPF-файлу                    |
| OutDir   | нет          | `src`        | Каталог для выгрузки исходников     |

## Параметры подключения (обязательно)

Разборка EPF/ERF требует базы с исходной конфигурацией, иначе ссылочные типы теряются. Обязательно примени `test-databases`, выбери разрешённую запись и передай параметры только из неё. Не используй временную пустую базу, произвольное подключение или `.v8-project.json` как источник подключения. Если подходящей записи нет, остановись и сообщи пользователю.
## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/epf-dump/scripts/epf-dump.ps1 <параметры>
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
| `-InputFile <путь>` | да | Путь к EPF/ERF-файлу |
| `-OutputDir <путь>` | да | Каталог для выгрузки исходников |
| `-Format <формат>` | нет | `Hierarchical` (по умолч.) / `Plain` |

> `*` — обязательно хотя бы одно подключение. Без базы скрипт завершится с ошибкой (dump в пустой базе безвозвратно теряет ссылочные типы)

## Примеры

```powershell
# Разборка обработки (файловая база)
powershell.exe -NoProfile -File <skills-root>/epf-dump/scripts/epf-dump.ps1 -InfoBasePath "C:\Bases\MyDB" -InputFile "build/МояОбработка.epf" -OutputDir "src"

# Серверная база
powershell.exe -NoProfile -File <skills-root>/epf-dump/scripts/epf-dump.ps1 -InfoBaseServer "srv01" -InfoBaseRef "MyDB" -UserName "Admin" -Password "secret" -InputFile "build/МояОбработка.epf" -OutputDir "src"
```
