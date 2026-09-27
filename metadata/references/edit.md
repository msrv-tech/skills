# edit — точечное редактирование метаданных 1С

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/metadata/scripts/edit.py" \
  -ObjectPath <project-root>/src/Object.xml \
  -Operation modify-property -Value "CodeLength=11"
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/metadata/scripts/edit.ps1" -ObjectPath <project-root>/src/Object.xml
```
<!-- docs-evals:python-entrypoint:end -->

Атомарные операции модификации существующих XML объектов метаданных.

## Команда

### Inline mode (простые операции)

Linux:

```bash
python3 <skills-root>/metadata/scripts/edit.py \
  -ObjectPath "<path>" -Operation <op> -Value "<val>"
```

Windows:

```powershell
powershell.exe -NoProfile -File <skills-root>/metadata/scripts/edit.ps1 -ObjectPath "<path>" -Operation <op> -Value "<val>"
```

### JSON mode (сложные/комбинированные)

Linux:

```bash
python3 <skills-root>/metadata/scripts/edit.py \
  -DefinitionFile "<json>" -ObjectPath "<path>"
```

Windows:

```powershell
powershell.exe -NoProfile -File <skills-root>/metadata/scripts/edit.ps1 -DefinitionFile "<json>" -ObjectPath "<path>"
```

| Параметр | Описание |
|----------|----------|
| ObjectPath | XML-файл или директория объекта (обязательный, авторезолв `<dirName>.xml`) |
| Operation | Inline-операция (альтернатива DefinitionFile) |
| Value | Значение для inline-операции |
| DefinitionFile | JSON-файл с операциями (альтернатива Operation) |
| NoValidate | Не запускать metadata:validate после правки |

## Операции — сводная таблица

Batch через `;;` во всех операциях. Подробный синтаксис — в файлах по ссылкам.

### Дочерние элементы — [edit-child-operations.md](edit-child-operations.md)

| Операция | Формат Value | Пример |
|----------|-------------|--------|
| `add-attribute` | `Имя: Тип \| флаги` | `"Сумма: Число(15,2) \| req, index"` |
| `add-ts` | `ТЧ: Рекв1: Тип1, Рекв2: Тип2` | `"Товары: Ном: CatalogRef.Ном, Кол: Число(15,3)"` |
| `add-dimension` | `Имя: Тип \| флаги` | `"Организация: CatalogRef.Организации \| master"` |
| `add-resource` | `Имя: Тип` | `"Сумма: Число(15,2)"` |
| `add-enumValue` | `Имя` | `"Значение1 ;; Значение2"` |
| `add-column` | `Имя: Тип` | `"Тип: EnumRef.ТипыДокументов"` |
| `add-form` / `add-template` / `add-command` | `Имя` | `"ФормаЭлемента"` |
| `add-ts-attribute` | `ТЧ.Имя: Тип` | `"Товары.Скидка: Число(15,2)"` |
| `remove-*` | `Имя` | `"СтарыйРеквизит ;; ЕщёОдин"` |
| `remove-ts-attribute` | `ТЧ.Имя` | `"Товары.УстаревшийРекв"` |
| `modify-attribute` | `Имя: ключ=значение` | `"СтароеИмя: name=НовоеИмя, type=Строка(500)"` |
| `modify-ts-attribute` | `ТЧ.Имя: ключ=значение` | `"Товары.Рекв: name=НовоеИмя"` |
| `modify-ts` | `ТЧ: ключ=значение` | `"Товары: synonym=Товарный состав"` |

Позиционная вставка: `"Склад: CatalogRef.Склады >> after Организация"`.

### Свойства объекта — [edit-properties.md](edit-properties.md)

| Операция | Формат Value | Пример |
|----------|-------------|--------|
| `modify-property` | `Ключ=Значение` | `"CodeLength=11 ;; DescriptionLength=150"` |
| `add-owner` | `MetaType.Name` | `"Catalog.Контрагенты ;; Catalog.Организации"` |
| `add-registerRecord` | `MetaType.Name` | `"AccumulationRegister.ОстаткиТоваров"` |
| `add-basedOn` | `MetaType.Name` | `"Document.ЗаказКлиента"` |
| `add-inputByString` | `Путь поля` | `"StandardAttribute.Description"` |
| `set-owners` / `set-registerRecords` / `set-basedOn` / `set-inputByString` | Замена всего списка | `"Catalog.Орг ;; Catalog.Контр"` |
| `remove-owner` / `remove-registerRecord` / ... | Удаление из списка | `"Catalog.Контрагенты"` |

### JSON DSL — [edit-json-dsl.md](edit-json-dsl.md)

Для комбинированных операций (add + remove + modify в одном файле), синонимы ключей/типов, таблица поддерживаемых объектов.

## Быстрые примеры

Следующие фрагменты аргументов одинаковы для Python CLI и PowerShell:

```text
# Добавить реквизиты
-Operation add-attribute -Value "Комментарий: Строка(200) ;; Сумма: Число(15,2) | index"

# Составной тип (несколько типов через +)
-Operation add-attribute -Value "Значение: Строка + Число(15,2) + Дата + CatalogRef.Контрагенты"

# Добавить ТЧ с реквизитами
-Operation add-ts -Value "Товары: Ном: CatalogRef.Ном | req, Кол: Число(15,3), Цена: Число(15,2)"

# Удалить реквизит
-Operation remove-attribute -Value "УстаревшийРеквизит"

# Переименовать + сменить тип
-Operation modify-attribute -Value "СтароеИмя: name=НовоеИмя, type=Строка(500)"

# Изменить свойства объекта
-Operation modify-property -Value "CodeLength=11 ;; DescriptionLength=150"

# Владельцы справочника
-Operation set-owners -Value "Catalog.Контрагенты ;; Catalog.Организации"
```

## Верификация

```
/metadata:validate <ObjectPath>    — валидация после редактирования
/metadata:inspect <ObjectPath>        — визуальная сводка
```
