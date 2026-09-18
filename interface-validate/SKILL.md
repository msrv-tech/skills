---
name: interface-validate
description: Валидация командного интерфейса 1С. Используй после настройки командного интерфейса подсистемы для проверки корректности
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /interface-validate — валидация CommandInterface.xml

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/interface-validate/scripts/interface-validate.py" -CIPath <project-root>/CommandInterface.xml
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/interface-validate/scripts/interface-validate.ps1" -CIPath <project-root>/CommandInterface.xml
```
<!-- docs-evals:python-entrypoint:end -->

Проверяет XML командного интерфейса на структурные ошибки: корневой элемент, допустимые секции, порядок, формат ссылок на команды, дубликаты.

## Параметры

| Параметр  | Обяз. | Умолч. | Описание                                |
|-----------|:-----:|---------|-----------------------------------------|
| CIPath    | да    | —       | Путь к CommandInterface.xml             |
| Detailed  | нет   | —       | Подробный вывод (все проверки, включая успешные) |
| MaxErrors | нет   | 30      | Остановиться после N ошибок              |
| OutFile   | нет   | —       | Записать результат в файл (UTF-8 BOM)   |

## Команда

```powershell
powershell.exe -NoProfile -File "<skills-root>/interface-validate/scripts/interface-validate.ps1" -CIPath "Subsystems/Продажи"
powershell.exe -NoProfile -File "<skills-root>/interface-validate/scripts/interface-validate.ps1" -CIPath "Subsystems/Продажи/Ext/CommandInterface.xml"
```
