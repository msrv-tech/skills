---
name: meta-validate
description: Валидация объекта метаданных 1С. Используй после создания или модификации объекта конфигурации для проверки корректности
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /meta-validate — валидация объекта метаданных 1С

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/meta-validate/scripts/meta-validate.py" -ObjectPath <project-root>/src/Object.xml
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/meta-validate/scripts/meta-validate.ps1" -ObjectPath <project-root>/src/Object.xml
```
<!-- docs-evals:python-entrypoint:end -->

Проверяет XML объекта метаданных из выгрузки конфигурации на структурные ошибки.

## Параметры

| Параметр   | Обяз. | Умолч. | Описание                                      |
|------------|:-----:|---------|-------------------------------------------------|
| ObjectPath | да    | —       | Путь к XML-файлу или каталогу. Через `\|` для batch |
| Detailed   | нет   | —       | Подробный вывод (все проверки, включая успешные) |
| MaxErrors  | нет   | 30      | Остановиться после N ошибок (per object)        |
| OutFile    | нет   | —       | Записать результат в файл (UTF-8 BOM)           |

## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/meta-validate/scripts/meta-validate.ps1 -ObjectPath "Catalogs/Номенклатура/Номенклатура.xml"
powershell.exe -NoProfile -File <skills-root>/meta-validate/scripts/meta-validate.ps1 -ObjectPath "Catalogs/Банки|Documents/Заказ"
```
