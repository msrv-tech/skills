---
name: epf-validate
description: Валидация внешней обработки 1С (EPF). Используй после создания или модификации обработки для проверки корректности
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /epf-validate — валидация внешней обработки (EPF)

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/epf-validate/scripts/epf-validate.py" -ObjectPath <project-root>/src/Object.xml
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/epf-validate/scripts/epf-validate.ps1" -ObjectPath <project-root>/src/Object.xml
```
<!-- docs-evals:python-entrypoint:end -->

Проверяет структурную корректность XML-исходников внешней обработки: корневую структуру, InternalInfo, свойства, ChildObjects, реквизиты, табличные части, уникальность имён, наличие файлов форм и макетов. Также работает для внешних отчётов (ERF).

## Параметры

| Параметр   | Обяз. | Умолч. | Описание                                      |
|------------|:-----:|---------|-------------------------------------------------|
| ObjectPath | да    | —       | Путь к корневому XML или каталогу обработки     |
| Detailed   | нет   | —       | Подробный вывод (все проверки, включая успешные) |
| MaxErrors  | нет   | 30      | Остановиться после N ошибок                     |
| OutFile    | нет   | —       | Записать результат в файл (UTF-8 BOM)           |

## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/epf-validate/scripts/epf-validate.ps1 -ObjectPath "src/МояОбработка"
powershell.exe -NoProfile -File <skills-root>/epf-validate/scripts/epf-validate.ps1 -ObjectPath "src/МояОбработка/МояОбработка.xml"
```

