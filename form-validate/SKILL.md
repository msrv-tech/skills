---
name: form-validate
description: Валидация управляемой формы 1С. Используй после создания или модификации формы для проверки корректности. При наличии BaseForm автоматически проверяет callType и ID расширений
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /form-validate — валидация управляемой формы 1С

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/form-validate/scripts/form-validate.py" -FormPath <project-root>/Form.xml
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/form-validate/scripts/form-validate.ps1" -FormPath <project-root>/Form.xml
```
<!-- docs-evals:python-entrypoint:end -->

Проверяет Form.xml на структурные ошибки: уникальность ID, наличие companion-элементов, корректность ссылок DataPath и команд.

## Параметры

| Параметр  | Обяз. | Умолч. | Описание                                |
|-----------|:-----:|---------|-----------------------------------------|
| FormPath  | да    | —       | Путь к файлу Form.xml                   |
| Detailed  | нет   | —       | Подробный вывод (все проверки, включая успешные) |
| MaxErrors | нет   | 30      | Остановиться после N ошибок              |

## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/form-validate/scripts/form-validate.ps1 -FormPath "Catalogs/Номенклатура/Forms/ФормаЭлемента"
powershell.exe -NoProfile -File <skills-root>/form-validate/scripts/form-validate.ps1 -FormPath "src/МояОбработка/Forms/Форма/Ext/Form.xml"
```

