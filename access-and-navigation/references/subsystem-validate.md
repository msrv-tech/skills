# access-and-navigation:subsystem-validate — валидация подсистемы 1С

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/access-and-navigation/scripts/subsystem-validate.py" -SubsystemPath <project-root>/Subsystem.xml
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/access-and-navigation/scripts/subsystem-validate.ps1" -SubsystemPath <project-root>/Subsystem.xml
```
<!-- docs-evals:python-entrypoint:end -->

Проверяет структурную корректность XML-файла подсистемы из выгрузки конфигурации.

## Параметры

| Параметр      | Обяз. | Умолч. | Описание                                  |
|---------------|:-----:|---------|--------------------------------------------|
| SubsystemPath | да    | —       | Путь к XML-файлу подсистемы                |
| Detailed      | нет   | —       | Подробный вывод (все проверки, включая успешные) |
| MaxErrors     | нет   | 30      | Остановиться после N ошибок                |
| OutFile       | нет   | —       | Записать результат в файл                  |

## Команда

```powershell
powershell.exe -NoProfile -File "<skills-root>/access-and-navigation/scripts/subsystem-validate.ps1" -SubsystemPath "Subsystems/Продажи"
powershell.exe -NoProfile -File "<skills-root>/access-and-navigation/scripts/subsystem-validate.ps1" -SubsystemPath "Subsystems/Продажи.xml"
```
