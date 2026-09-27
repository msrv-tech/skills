---
name: metadata
description: >-
  Создание, анализ, изменение, удаление и проверка объектов метаданных 1С, включая встроенную справку.
allowed-tools:
  - Read
  - Glob
  - Bash
---

# metadata

Выбери один режим по намерению пользователя и полностью прочитай только его
инструкцию. Не загружай остальные references без необходимости.
| Режим | Назначение | Детали | Исполняемые точки входа |
|---|---|---|---|
| `create` | Создать объект метаданных | [инструкция](references/create.md) | `scripts/create.ps1`, `scripts/create.py` |
| `inspect` | Проанализировать объект | [инструкция](references/inspect.md) | `scripts/inspect-metadata.ps1`, `scripts/inspect-metadata.py` |
| `edit` | Изменить объект | [инструкция](references/edit.md) | `scripts/edit.ps1`, `scripts/edit.py` |
| `remove` | Удалить объект | [инструкция](references/remove.md) | `scripts/remove.ps1`, `scripts/remove.py` |
| `validate` | Проверить объект | [инструкция](references/validate.md) | `scripts/validate.ps1`, `scripts/validate.py` |
| `add-help` | Добавить встроенную справку | [инструкция](references/add-help.md) | `scripts/add-help.ps1`, `scripts/add-help.py` |

После изменяющего режима выполни профильную валидацию, если инструкция режима
не включает равнозначную проверку. Скрипты запускай из этого доменного каталога.
