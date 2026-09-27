---
name: reports
description: >-
  Создание и изменение СКД, анализ отчётов и разработка запросов 1С.
allowed-tools:
  - Read
  - Glob
  - Bash
---

# reports

Выбери один режим по намерению пользователя и полностью прочитай только его
инструкцию. Не загружай остальные references без необходимости.
| Режим | Назначение | Детали | Исполняемые точки входа |
|---|---|---|---|
| `skd-create` | Создать СКД | [инструкция](references/skd-create.md) | `scripts/skd-create.ps1`, `scripts/skd-create.py` |
| `skd-decompile` | Получить JSON-черновик из СКД | [инструкция](references/skd-decompile.md) | `scripts/skd-decompile.ps1`, `scripts/skd-decompile.py` |
| `skd-inspect` | Проанализировать СКД | [инструкция](references/skd-inspect.md) | `scripts/skd-inspect.ps1`, `scripts/skd-inspect.py` |
| `skd-edit` | Изменить СКД | [инструкция](references/skd-edit.md) | `scripts/skd-edit.ps1`, `scripts/skd-edit.py` |
| `skd-validate` | Проверить СКД | [инструкция](references/skd-validate.md) | `scripts/skd-validate.ps1`, `scripts/skd-validate.py` |
| `query` | Составить или оптимизировать запрос | [инструкция](references/query.md) | — |

После изменяющего режима выполни профильную валидацию, если инструкция режима
не включает равнозначную проверку. Скрипты запускай из этого доменного каталога.
