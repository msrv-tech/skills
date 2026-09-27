---
name: configuration
description: >-
  Создание, анализ, изменение и проверка конфигураций 1С.
allowed-tools:
  - Read
  - Glob
  - Bash
---

# configuration

Выбери один режим по намерению пользователя и полностью прочитай только его
инструкцию. Не загружай остальные references без необходимости.
| Режим | Назначение | Детали | Исполняемые точки входа |
|---|---|---|---|
| `create-empty` | Создать пустую конфигурацию | [инструкция](references/create-empty.md) | `scripts/create.ps1`, `scripts/create.py` |
| `create-project` | Создать прикладное решение целиком | [инструкция](references/create-project.md) | — |
| `add-object` | Добавить объект с формой и подсистемой | [инструкция](references/add-object.md) | — |
| `inspect` | Изучить состав конфигурации | [инструкция](references/inspect.md) | `scripts/inspect-configuration.ps1`, `scripts/inspect-configuration.py` |
| `edit` | Изменить свойства или состав | [инструкция](references/edit.md) | `scripts/edit.ps1`, `scripts/edit.py` |
| `validate` | Проверить XML конфигурации | [инструкция](references/validate.md) | `scripts/validate.ps1`, `scripts/validate.py` |

После изменяющего режима выполни профильную валидацию, если инструкция режима
не включает равнозначную проверку. Скрипты запускай из этого доменного каталога.
