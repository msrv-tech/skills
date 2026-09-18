---
name: cf-validate
description: Валидация конфигурации 1С. Используй после создания или модификации конфигурации для проверки корректности
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /cf-validate — валидация конфигурации 1С

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/cf-validate/scripts/cf-validate.py" -ConfigPath <project-root>/src
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/cf-validate/scripts/cf-validate.ps1" -ConfigPath <project-root>/src
```
<!-- docs-evals:python-entrypoint:end -->

Проверяет Configuration.xml на структурные ошибки: XML well-formedness, InternalInfo, свойства, enum-значения, ChildObjects, DefaultLanguage, файлы языков, каталоги объектов.

## Параметры

| Параметр   | Обяз. | Умолч. | Описание                                      |
|------------|:-----:|---------|-------------------------------------------------|
| ConfigPath | да    | —       | Путь к Configuration.xml или каталогу выгрузки  |
| Detailed   | нет   | —       | Подробный вывод (все проверки, включая успешные) |
| MaxErrors  | нет   | 30      | Остановиться после N ошибок                     |
| OutFile    | нет   | —       | Записать результат в файл (UTF-8 BOM)           |

## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/cf-validate/scripts/cf-validate.ps1 -ConfigPath "upload/cfempty"
powershell.exe -NoProfile -File <skills-root>/cf-validate/scripts/cf-validate.ps1 -ConfigPath "upload/cfempty/Configuration.xml"
```
