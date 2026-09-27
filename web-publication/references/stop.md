# stop — Остановка Apache

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/web-publication/scripts/stop.py" -ApachePath <ApachePath>
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/web-publication/scripts/stop.ps1" -ApachePath <ApachePath>
```
<!-- docs-evals:python-entrypoint:end -->

Останавливает Apache HTTP Server. Публикации сохраняются — при следующем `/web-publication:publish` сервер запустится снова.

## Usage

```
/web-publication:stop
```

## Параметры подключения

Прочитай `.v8-project.json` из корня проекта. Если задан `webPath` — используй как `-ApachePath`.
По умолчанию `tools/apache24` от корня проекта.

## Команда

Ubuntu:

```bash
python3 <skills-root>/web-publication/scripts/stop.py
```

На общей системной Apache скрипт не останавливает `apache2.service`: он
отключает только ссылки `1c-skills-*.conf`, проверяет конфигурацию и выполняет
reload. Файлы публикаций сохраняются, чужие сайты и публикации не изменяются.

Windows:

```powershell
powershell.exe -NoProfile -File <skills-root>/web-publication/scripts/stop.ps1 <параметры>
```

### Параметры скрипта

| Параметр | Обязательный | Описание |
|----------|:------------:|----------|
| `-ApachePath <путь>` | нет | Корень Apache (по умолчанию `tools/apache24`) |

## После выполнения

Предложи пользователю:
- **Перезапуск** — `/web-publication:publish <база>` (повторный вызов поднимет Apache с существующими публикациями)
- **Удаление публикаций** — `/web-publication:unpublish <имя>` или `/web-publication:unpublish --all`

## Примеры

```powershell
# Остановить Apache
powershell.exe -NoProfile -File <skills-root>/web-publication/scripts/stop.ps1

# С указанием пути
powershell.exe -NoProfile -File <skills-root>/web-publication/scripts/stop.ps1 -ApachePath "C:\tools\apache24"
```
