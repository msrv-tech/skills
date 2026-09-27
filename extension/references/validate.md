# validate — валидация расширения конфигурации (CFE)

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/extension/scripts/validate.py" -ExtensionPath <project-root>/extension
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/extension/scripts/validate.ps1" -ExtensionPath <project-root>/extension
```
<!-- docs-evals:python-entrypoint:end -->

Проверяет структурную корректность расширения: XML-формат, свойства, состав, заимствованные объекты. Аналог `/configuration:validate`, но для расширений.

## Параметры

| Параметр      | Обяз. | Умолч. | Описание                                        |
|---------------|:-----:|---------|-------------------------------------------------|
| ExtensionPath | да    | —       | Путь к каталогу или Configuration.xml расширения |
| Detailed      | нет   | —       | Подробный вывод (все проверки, включая успешные)  |
| MaxErrors     | нет   | 30      | Остановиться после N ошибок                      |
| OutFile       | нет   | —       | Записать результат в файл                        |

## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/extension/scripts/validate.ps1 -ExtensionPath "src"
powershell.exe -NoProfile -File <skills-root>/extension/scripts/validate.ps1 -ExtensionPath "src/Configuration.xml"
```
