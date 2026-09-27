# role-inspect — анализ роли 1С

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/access-and-navigation/scripts/role-inspect.py" -RightsPath <project-root>/Rights.xml
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/access-and-navigation/scripts/role-inspect.ps1" -RightsPath <project-root>/Rights.xml
```
<!-- docs-evals:python-entrypoint:end -->

Парсит `Rights.xml` роли и выдаёт компактную сводку: объекты сгруппированы по типу, показаны только разрешённые права. Сжатие: тысячи строк XML → 50–150 строк текста.

## Использование

```
/access-and-navigation:role-inspect <RightsPath>
```

**RightsPath** — путь к файлу `Rights.xml` роли (обычно `Roles/ИмяРоли/Ext/Rights.xml`).

## Запуск скрипта

```powershell
powershell.exe -NoProfile -File <skills-root>/access-and-navigation/scripts/role-inspect.ps1 -RightsPath <path> -OutFile <output.txt>
```

### Параметры

| Параметр | Обязательный | Описание |
|----------|:------------:|----------|
| `-RightsPath` | да | Путь к Rights.xml |
| `-ShowDenied` | нет | Показать запрещённые права (по умолчанию скрыты) |
| `-Limit` | нет | Макс. строк вывода (по умолчанию `150`). `0` = без ограничений |
| `-Offset` | нет | Пропустить N строк — для пагинации (по умолчанию `0`) |
| `-OutFile` | нет | Записать результат в файл (UTF-8 BOM). Без этого — вывод в консоль |

**Важно:** Всегда используй `-OutFile` и читай результат через Read tool. Прямой вывод в консоль через bash ломает кириллицу.

Для большой роли при усечении вывода:
```powershell
... -Offset 150            # пагинация: пропустить первые 150 строк
```

