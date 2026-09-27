---
name: external-artifacts
description: >-
  Создание, сборка, разборка и проверка внешних обработок EPF и отчётов ERF.
allowed-tools:
  - Read
  - Glob
  - Bash
---

# external-artifacts

Выбери один режим по намерению пользователя и полностью прочитай только его
инструкцию. Не загружай остальные references без необходимости.
| Режим | Назначение | Детали | Исполняемые точки входа |
|---|---|---|---|
| `epf-create` | Создать исходники EPF | [инструкция](references/epf-create.md) | `scripts/epf-create.ps1`, `scripts/epf-create.py` |
| `epf-full-cycle` | Выполнить полный цикл EPF | [инструкция](references/epf-full-cycle.md) | — |
| `erf-create` | Создать исходники ERF | [инструкция](references/erf-create.md) | `scripts/erf-create.ps1`, `scripts/erf-create.py` |
| `build` | Собрать EPF или ERF | [инструкция](references/build.md) | `scripts/build.ps1`, `scripts/build.py` |
| `dump` | Разобрать EPF или ERF | [инструкция](references/dump.md) | `scripts/dump.ps1`, `scripts/dump.py` |
| `validate` | Проверить XML внешнего артефакта | [инструкция](references/validate.md) | `scripts/validate.ps1`, `scripts/validate.py` |
| `bsp-register` | Добавить регистрацию БСП | [инструкция](references/bsp-register.md) | — |
| `bsp-command` | Добавить команду БСП | [инструкция](references/bsp-command.md) | — |

После изменяющего режима выполни профильную валидацию, если инструкция режима
не включает равнозначную проверку. Скрипты запускай из этого доменного каталога.
