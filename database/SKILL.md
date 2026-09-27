---
name: database
description: >-
  Создание, запуск, обновление, загрузка и выгрузка информационных баз 1С, Git и ibcmd.
allowed-tools:
  - Read
  - Glob
  - Bash
---

# database

Выбери один режим по намерению пользователя и полностью прочитай только его
инструкцию. Не загружай остальные references без необходимости.
Для любой существующей базы сначала используй `test-databases`.

| Режим | Назначение | Детали | Исполняемые точки входа |
|---|---|---|---|
| `create` | Создать информационную базу | [инструкция](references/create.md) | `scripts/create.ps1`, `scripts/create.py` |
| `project-settings` | Прочитать или изменить настройки проекта | [инструкция](references/project-settings.md) | — |
| `run` | Запустить 1С:Предприятие | [инструкция](references/run.md) | `scripts/run.ps1`, `scripts/run.py` |
| `update` | Применить конфигурацию к базе | [инструкция](references/update.md) | `scripts/update.ps1`, `scripts/update.py` |
| `load-xml` | Загрузить XML-исходники | [инструкция](references/load-xml.md) | `scripts/load-xml.ps1`, `scripts/load-xml.py` |
| `dump-xml` | Выгрузить XML-исходники | [инструкция](references/dump-xml.md) | `scripts/dump-xml.ps1`, `scripts/dump-xml.py` |
| `load-cf` | Загрузить CF или CFE | [инструкция](references/load-cf.md) | `scripts/load-cf.ps1`, `scripts/load-cf.py` |
| `dump-cf` | Выгрузить CF или CFE | [инструкция](references/dump-cf.md) | `scripts/dump-cf.ps1`, `scripts/dump-cf.py` |
| `load-git` | Применить изменения Git | [инструкция](references/load-git.md) | `scripts/load-git.ps1`, `scripts/load-git.py` |
| `repository-update` | Получить изменения из хранилища 1С | [инструкция](references/repository-update.md) | `scripts/repository-update.ps1`, `scripts/repository-update.py` |
| `ibcmd` | Собрать или обновить через ibcmd | [инструкция](references/ibcmd.md) | — |

После изменяющего режима выполни профильную валидацию, если инструкция режима
не включает равнозначную проверку. Скрипты запускай из этого доменного каталога.
