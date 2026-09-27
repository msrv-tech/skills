---
name: layouts
description: >-
  Создание, декомпиляция и проверка MXL, а также подключение макетов к объектам 1С.
allowed-tools:
  - Read
  - Glob
  - Bash
---

# layouts

Выбери один режим по намерению пользователя и полностью прочитай только его
инструкцию. Не загружай остальные references без необходимости.
| Режим | Назначение | Детали | Исполняемые точки входа |
|---|---|---|---|
| `mxl-create` | Создать MXL из JSON | [инструкция](references/mxl-create.md) | `scripts/mxl-create.ps1`, `scripts/mxl-create.py` |
| `mxl-decompile` | Получить JSON из MXL | [инструкция](references/mxl-decompile.md) | `scripts/mxl-decompile.ps1`, `scripts/mxl-decompile.py` |
| `mxl-inspect` | Проанализировать MXL | [инструкция](references/mxl-inspect.md) | `scripts/mxl-inspect.ps1`, `scripts/mxl-inspect.py` |
| `mxl-validate` | Проверить MXL | [инструкция](references/mxl-validate.md) | `scripts/mxl-validate.ps1`, `scripts/mxl-validate.py` |
| `attach` | Добавить макет к объекту | [инструкция](references/attach.md) | `scripts/attach.ps1`, `scripts/attach.py` |
| `remove` | Удалить макет | [инструкция](references/remove.md) | `scripts/remove.ps1`, `scripts/remove.py` |

После изменяющего режима выполни профильную валидацию, если инструкция режима
не включает равнозначную проверку. Скрипты запускай из этого доменного каталога.
