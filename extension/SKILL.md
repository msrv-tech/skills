---
name: extension
description: >-
  Создание, заимствование, перехват методов, анализ и проверка расширений 1С CFE.
allowed-tools:
  - Read
  - Glob
  - Bash
---

# extension

Выбери один режим по намерению пользователя и полностью прочитай только его
инструкцию. Не загружай остальные references без необходимости.
| Режим | Назначение | Детали | Исполняемые точки входа |
|---|---|---|---|
| `create` | Создать расширение | [инструкция](references/create.md) | `scripts/create.ps1`, `scripts/create.py` |
| `full-cycle` | Выполнить полный цикл разработки CFE | [инструкция](references/full-cycle.md) | — |
| `borrow` | Заимствовать объект базовой конфигурации | [инструкция](references/borrow.md) | `scripts/borrow.ps1`, `scripts/borrow.py` |
| `patch-method` | Добавить перехватчик метода | [инструкция](references/patch-method.md) | `scripts/patch-method.ps1`, `scripts/patch-method.py` |
| `inspect` | Проанализировать состав и переносы | [инструкция](references/inspect.md) | `scripts/inspect-extension.ps1`, `scripts/inspect-extension.py` |
| `validate` | Проверить расширение | [инструкция](references/validate.md) | `scripts/validate.ps1`, `scripts/validate.py` |

После изменяющего режима выполни профильную валидацию, если инструкция режима
не включает равнозначную проверку. Скрипты запускай из этого доменного каталога.
