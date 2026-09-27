# dump — Разборка обработки

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/external-artifacts/scripts/dump.py" -InfoBasePath <test-infobase-path>
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/external-artifacts/scripts/dump.ps1" -InfoBasePath <test-infobase-path>
```
<!-- docs-evals:python-entrypoint:end -->

## Usage

```
/external-artifacts:dump <EpfFile> [OutDir]
```

| Параметр | Обязательный | По умолчанию | Описание                            |
|----------|:------------:|--------------|-------------------------------------|
| EpfFile  | да           | —            | Путь к EPF-файлу                    |
| OutDir   | нет          | `src`        | Каталог для выгрузки исходников     |

## Параметры подключения (обязательно)

Разборка EPF/ERF требует базы с исходной конфигурацией, иначе ссылочные типы теряются. Обязательно примени `test-databases`, выбери разрешённую запись и передай параметры только из неё. Не используй временную пустую базу, произвольное подключение или `.v8-project.json` как источник подключения. Если подходящей записи нет, остановись и сообщи пользователю.
## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/external-artifacts/scripts/dump.ps1 <параметры>
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
powershell.exe -NoProfile -File <skills-root>/external-artifacts/scripts/dump.ps1 -InfoBasePath "C:\Bases\MyDB" -InputFile "build/МояОбработка.epf" -OutputDir "src"

# Серверная база
powershell.exe -NoProfile -File <skills-root>/external-artifacts/scripts/dump.ps1 -InfoBaseServer "srv01" -InfoBaseRef "MyDB" -UserName "Admin" -Password "secret" -InputFile "build/МояОбработка.epf" -OutputDir "src"
```
