---
name: access-and-navigation
description: >-
  Роли, RLS, подсистемы и командный интерфейс 1С: создание, анализ, изменение и проверка.
allowed-tools:
  - Read
  - Glob
  - Bash
---

# access-and-navigation

Выбери один режим по намерению пользователя и полностью прочитай только его
инструкцию. Не загружай остальные references без необходимости.
| Режим | Назначение | Детали | Исполняемые точки входа |
|---|---|---|---|
| `role-create` | Создать роль | [инструкция](references/role-create.md) | `scripts/role-create.ps1`, `scripts/role-create.py` |
| `role-inspect` | Проанализировать права и RLS | [инструкция](references/role-inspect.md) | `scripts/role-inspect.ps1`, `scripts/role-inspect.py` |
| `role-validate` | Проверить роль | [инструкция](references/role-validate.md) | `scripts/role-validate.ps1`, `scripts/role-validate.py` |
| `subsystem-create` | Создать подсистему | [инструкция](references/subsystem-create.md) | `scripts/subsystem-create.ps1`, `scripts/subsystem-create.py` |
| `subsystem-inspect` | Проанализировать подсистему | [инструкция](references/subsystem-inspect.md) | `scripts/subsystem-inspect.ps1`, `scripts/subsystem-inspect.py` |
| `subsystem-edit` | Изменить подсистему | [инструкция](references/subsystem-edit.md) | `scripts/subsystem-edit.ps1`, `scripts/subsystem-edit.py` |
| `subsystem-validate` | Проверить подсистему | [инструкция](references/subsystem-validate.md) | `scripts/subsystem-validate.ps1`, `scripts/subsystem-validate.py` |
| `interface-edit` | Изменить командный интерфейс | [инструкция](references/interface-edit.md) | `scripts/interface-edit.ps1`, `scripts/interface-edit.py` |
| `interface-validate` | Проверить командный интерфейс | [инструкция](references/interface-validate.md) | `scripts/interface-validate.ps1`, `scripts/interface-validate.py` |

После изменяющего режима выполни профильную валидацию, если инструкция режима
не включает равнозначную проверку. Скрипты запускай из этого доменного каталога.
