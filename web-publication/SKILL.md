---
name: web-publication
description: >-
  Публикация информационных баз 1С через Apache, проверка состояния и удаление публикаций.
allowed-tools:
  - Read
  - Glob
  - Bash
---

# web-publication

Выбери один режим по намерению пользователя и полностью прочитай только его
инструкцию. Не загружай остальные references без необходимости.
| Режим | Назначение | Детали | Исполняемые точки входа |
|---|---|---|---|
| `publish` | Опубликовать базу через Apache | [инструкция](references/publish.md) | `scripts/publish.ps1`, `scripts/publish.py` |
| `inspect` | Проверить сервер и публикации | [инструкция](references/inspect.md) | `scripts/inspect-publication.ps1`, `scripts/inspect-publication.py` |
| `unpublish` | Удалить публикацию | [инструкция](references/unpublish.md) | `scripts/unpublish.ps1`, `scripts/unpublish.py` |
| `stop` | Остановить Apache | [инструкция](references/stop.md) | `scripts/stop.ps1`, `scripts/stop.py` |

После изменяющего режима выполни профильную валидацию, если инструкция режима
не включает равнозначную проверку. Скрипты запускай из этого доменного каталога.
