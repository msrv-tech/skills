# build — Сборка обработки

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/external-artifacts/scripts/build.py" -InfoBasePath <test-infobase-path>
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/external-artifacts/scripts/build.ps1" -InfoBasePath <test-infobase-path>
```
<!-- docs-evals:python-entrypoint:end -->

## Usage

```
/external-artifacts:build <ProcessorName> [SrcDir] [OutDir]
```

| Параметр      | Обязательный | По умолчанию | Описание                             |
|---------------|:------------:|--------------|--------------------------------------|
| ProcessorName | да           | —            | Имя обработки (имя корневого XML)    |
| SrcDir        | нет          | `src`        | Каталог исходников                   |
| OutDir        | нет          | `build`      | Каталог для результата               |

## Параметры подключения (опционально)

Если нужна существующая ИБ, обязательно выбери её через `test-databases` и передай параметры только из разрешённой записи. Произвольные подключения и `.v8-project.json` как источник подключения запрещены.

Если метаданные реальной конфигурации не нужны, параметры подключения можно не задавать: скрипт создаст временную локальную базу со сгенерированными заглушками ссылочных типов и удалит её после сборки. Это не подключение к существующей ИБ.
## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/external-artifacts/scripts/build.ps1 <параметры>
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
| `-SourceFile <путь>` | да | Путь к корневому XML-файлу исходников |
| `-OutputFile <путь>` | да | Путь к выходному EPF/ERF-файлу |

> `*` — опционально. Если не указано — автоматически создаётся временная база со заглушками метаданных

## Примеры

```powershell
# Сборка обработки (файловая база)
powershell.exe -NoProfile -File <skills-root>/external-artifacts/scripts/build.ps1 -InfoBasePath "C:\Bases\MyDB" -SourceFile "src/МояОбработка.xml" -OutputFile "build/МояОбработка.epf"

# Серверная база
powershell.exe -NoProfile -File <skills-root>/external-artifacts/scripts/build.ps1 -InfoBaseServer "srv01" -InfoBaseRef "MyDB" -UserName "Admin" -Password "secret" -SourceFile "src/МояОбработка.xml" -OutputFile "build/МояОбработка.epf"
```
