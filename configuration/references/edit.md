# edit — редактирование конфигурации 1С

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/configuration/scripts/edit.py" -ConfigPath <project-root>/src
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/configuration/scripts/edit.ps1" -ConfigPath <project-root>/src
```
<!-- docs-evals:python-entrypoint:end -->

Точечное редактирование Configuration.xml: свойства, состав ChildObjects, роли по умолчанию.

## Параметры и команда

| Параметр | Описание |
|----------|----------|
| `ConfigPath` | Путь к Configuration.xml или каталогу выгрузки |
| `Operation` | Операция (см. таблицу) |
| `Value` | Значение для операции (batch через `;;`) |
| `DefinitionFile` | JSON-файл с массивом операций |
| `NoValidate` | Пропустить авто-валидацию |

```powershell
powershell.exe -NoProfile -File <skills-root>/configuration/scripts/edit.ps1 -ConfigPath '<path>' -Operation modify-property -Value 'Version=1.0.0.1'
```

## Операции

| Операция | Формат Value | Описание |
|----------|-------------|----------|
| `modify-property` | `Ключ=Значение` (batch `;;`) | Изменить свойство |
| `add-childObject` | `Type.Name` (batch `;;`) | Зарегистрировать уже существующий файл объекта в ChildObjects. Для создания нового объекта используй `/metadata:create`, `/access-and-navigation:role-create`, `/access-and-navigation:subsystem-create` — они регистрируют автоматически |
| `remove-childObject` | `Type.Name` (batch `;;`) | Удалить объект из ChildObjects |
| `add-defaultRole` | `Role.Name` или `Name` | Добавить роль по умолчанию |
| `remove-defaultRole` | `Role.Name` или `Name` | Удалить роль по умолчанию |
| `set-defaultRoles` | Имена через `;;` | Заменить список ролей по умолчанию |

Допустимые значения свойств, формат DefinitionFile (JSON), каноничный порядок: [edit-reference.md](edit-reference.md)

## Примеры

```powershell
# Изменить версию и поставщика
... -ConfigPath test-tmp/cf -Operation modify-property -Value "Version=1.0.0.1 ;; Vendor=Фирма 1С"

# Добавить объекты
... -ConfigPath test-tmp/cf -Operation add-childObject -Value "Catalog.Товары ;; Document.Заказ"

# Удалить объект
... -ConfigPath test-tmp/cf -Operation remove-childObject -Value "Catalog.Устаревший"

# Роли по умолчанию
... -ConfigPath test-tmp/cf -Operation add-defaultRole -Value "ПолныеПрава"
... -ConfigPath test-tmp/cf -Operation set-defaultRoles -Value "ПолныеПрава ;; Администратор"
```
