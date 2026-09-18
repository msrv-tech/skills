---
name: role-validate
description: Валидация роли 1С. Используй после создания или модификации роли для проверки корректности
allowed-tools:
  - Bash
  - Read
---

# /role-validate — валидация роли 1С

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/role-validate/scripts/role-validate.py" -RightsPath <project-root>/Rights.xml
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/role-validate/scripts/role-validate.ps1" -RightsPath <project-root>/Rights.xml
```
<!-- docs-evals:python-entrypoint:end -->

Проверяет корректность `Rights.xml` роли: формат XML, namespace, глобальные флаги, типы объектов, имена прав, RLS-ограничения, шаблоны. Опционально проверяет метаданные роли (UUID, имя, синоним).

## Параметры

| Параметр     | Обяз. | Умолч. | Описание                                        |
|--------------|:-----:|---------|-------------------------------------------------|
| RightsPath   | да    | —       | Путь к роли (директория или `Rights.xml`)        |
| Detailed     | нет   | —       | Подробный вывод (все проверки, включая успешные)  |
| MaxErrors    | нет   | 30      | Макс. ошибок до остановки (по умолчанию 30)      |
| OutFile      | нет   | —       | Записать результат в файл (UTF-8 BOM)            |

## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/role-validate/scripts/role-validate.ps1 -RightsPath "Roles/МояРоль"
```
