# create-empty — Создание пустой конфигурации 1С

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/configuration/scripts/create.py" -Name <Name> -Synonym <Synonym>
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/configuration/scripts/create.ps1" -Name <Name> -Synonym <Synonym>
```
<!-- docs-evals:python-entrypoint:end -->

Создаёт scaffold исходников пустой конфигурации 1С: `Configuration.xml`, `Languages/Русский.xml`.

## Параметры и команда

| Параметр | Описание |
|----------|----------|
| `Name` | Имя конфигурации (обязат.) |
| `Synonym` | Синоним (= Name если не указан) |
| `OutputDir` | Каталог для создания (default: `src`) |
| `Version` | Версия конфигурации |
| `Vendor` | Поставщик |
| `CompatibilityMode` | Режим совместимости (default: `Version8_3_24`) |

```powershell
powershell.exe -NoProfile -File <skills-root>/configuration/scripts/create.ps1 -Name "МояКонфигурация"
```

## Примеры

```powershell
# Базовая конфигурация
... -Name МояКонфигурация -Synonym "Моя конфигурация" -OutputDir test-tmp/cf

# С версией и поставщиком
... -Name TestCfg -Synonym "Тестовая" -Version "1.0.0.1" -Vendor "Фирма 1С" -OutputDir test-tmp/cf2

# Другой режим совместимости
... -Name TestCfg -CompatibilityMode Version8_3_27 -OutputDir test-tmp/cf3
```

## Верификация

```
/configuration:create-empty TestConfig -OutputDir test-tmp/cf
/configuration:inspect test-tmp/cf          — проверить созданное
/configuration:validate test-tmp/cf      — валидировать
```
