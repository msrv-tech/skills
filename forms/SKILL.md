---
name: forms
description: >-
  Создание, анализ, изменение, удаление и проверка управляемых форм 1С.
allowed-tools:
  - Read
  - Glob
  - Bash
---

# forms

Выбери один режим по намерению пользователя и полностью прочитай только его
инструкцию. Не загружай остальные references без необходимости.
| Режим | Назначение | Детали | Исполняемые точки входа |
|---|---|---|---|
| `add` | Добавить форму к объекту | [инструкция](references/add.md) | `scripts/add.ps1`, `scripts/add.py` |
| `create` | Скомпилировать форму из определения | [инструкция](references/create.md) | `scripts/create.ps1`, `scripts/create.py` |
| `inspect` | Проанализировать форму | [инструкция](references/inspect.md) | `scripts/inspect-form.ps1`, `scripts/inspect-form.py` |
| `edit` | Изменить существующую форму | [инструкция](references/edit.md) | `scripts/edit.ps1`, `scripts/edit.py` |
| `remove` | Удалить форму | [инструкция](references/remove.md) | `scripts/remove.ps1`, `scripts/remove.py` |
| `validate` | Проверить форму | [инструкция](references/validate.md) | `scripts/validate.ps1`, `scripts/validate.py` |
| `patterns` | Выбрать паттерн компоновки | [инструкция](references/patterns.md) | — |

После изменяющего режима выполни профильную валидацию, если инструкция режима
не включает равнозначную проверку. Скрипты запускай из этого доменного каталога.
