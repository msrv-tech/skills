# create — генерация объектов метаданных из JSON DSL

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/metadata/scripts/create.py" -JsonPath <project-root>/definition.json
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/metadata/scripts/create.ps1" -JsonPath <project-root>/definition.json
```
<!-- docs-evals:python-entrypoint:end -->

Принимает JSON-определение объекта метаданных → генерирует XML + модули в структуре выгрузки конфигурации + регистрирует в Configuration.xml.

## Порядок работы

1. Составь JSON по синтаксису и примерам ниже → запиши во временный файл
2. Запусти скрипт metadata:create
3. Если нужно изменить созданный объект — `/metadata:edit`
4. Если нужно проверить — `/metadata:validate`

## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/metadata/scripts/create.ps1 -JsonPath "<json>" -OutputDir "<ConfigDir>"
```

| Параметр | Описание |
|----------|----------|
| `JsonPath` | Путь к JSON-файлу (один объект `{...}` или массив `[{...}, ...]`) |
| `OutputDir` | Корень выгрузки конфигурации (где `Configuration.xml`, `Catalogs/`, `Documents/` и т.д.) |
| `FormatVersion` | Явная версия формата XML цели, например `2.20` или `2.21`. Имеет приоритет над автоопределением |
| `SourceConfigDir` | Каталог целевой выгрузки, по `Configuration.xml` которого определяется версия формата; удобен при генерации в отдельный каталог |

### Формат XML и отдельный каталог вывода

Скрипт определяет версию формата по `Configuration.xml` в `OutputDir` или выше. Если
`Configuration.xml` не найден, используется `2.17`, но теперь выводится предупреждение
в stderr — тихая подстановка убрана.

При безопасном workflow «сгенерировать объект в отдельный каталог → проверить diff →
перенести в выгрузку» версия из `OutputDir` не видна. В этом случае передай один из
параметров:

```bash
python3 metadata/scripts/create.py -JsonPath enum.json -OutputDir /tmp/new-object \
  -SourceConfigDir /path/to/target-dump
# или явно:
python3 metadata/scripts/create.py -JsonPath enum.json -OutputDir /tmp/new-object \
  -FormatVersion 2.20
```

Скрипт печатает выбранную версию и источник решения. Если `-SourceConfigDir` задан,
но `Configuration.xml` в нём и выше не найден, генерация завершается ошибкой.

## JSON DSL

### Общая структура

```json
{ "type": "Catalog", "name": "Номенклатура", ...свойства типа... }
```

`type` и `name` — обязательные. `synonym` генерируется из `name` автоматически (CamelCase → слова через пробел). Можно задать явно: `"synonym": "Мой синоним"`.

### Shorthand реквизитов

Используется в `attributes`, `dimensions`, `resources`, `tabularSections`:

```
"ИмяРеквизита"                    → String(10) по умолчанию
"ИмяРеквизита: Тип"               → с типом
"ИмяРеквизита: Тип | req, index"  → с флагами
```

Типы: `String(100)`, `Number(15,2)`, `Boolean`, `Date`, `DateTime`, `CatalogRef.Xxx`, `DocumentRef.Xxx`, `EnumRef.Xxx`, `DefinedType.Xxx` и др. ссылочные.

Составной тип: `"Значение: String + Number(15,2) + CatalogRef.Контрагенты"`.

Флаги: `req`, `index`, `indexAdditional`, `nonneg`, `master`, `mainFilter`, `denyIncomplete`, `useInTotals`.

### Свойства по типам

Примеров и shorthand-синтаксиса выше достаточно для типовых задач. Если нужны свойства типа, не показанные в примерах, и их допустимые значения — см. reference-файл:

- `types-basic.md` — Catalog, Document, Enum, Constant, DefinedType, Report, DataProcessor
- `types-registers.md` — InformationRegister, AccumulationRegister, AccountingRegister, CalculationRegister, ChartOfAccounts, ChartOfCharacteristicTypes, ChartOfCalculationTypes
- `types-process.md` — BusinessProcess, Task, ExchangePlan, CommonModule, ScheduledJob, EventSubscription, DocumentJournal
- `types-web.md` — HTTPService, WebService

Эта инструкция и reference-файлы — полная документация для генерации. Не ищи примеры XML в выгрузках конфигураций.

## Примеры паттернов DSL

### Минимальный объект

```json
{ "type": "Catalog", "name": "Валюты" }
```

### С реквизитами

```json
{
  "type": "Catalog", "name": "Организации",
  "descriptionLength": 100,
  "attributes": ["ИНН: String(12)", "КПП: String(9)", "Директор: CatalogRef.ФизическиеЛица"]
}
```

### С табличной частью

```json
{
  "type": "Document", "name": "ПриходнаяНакладная",
  "registerRecords": ["AccumulationRegister.ОстаткиТоваров"],
  "attributes": ["Организация: CatalogRef.Организации", "Контрагент: CatalogRef.Контрагенты"],
  "tabularSections": { "Товары": ["Номенклатура: CatalogRef.Номенклатура", "Количество: Number(15,3)", "Цена: Number(15,2)"] }
}
```

### Регистровый паттерн (измерения + ресурсы)

```json
{
  "type": "InformationRegister", "name": "КурсыВалют", "periodicity": "Day",
  "dimensions": ["Валюта: CatalogRef.Валюты | master, mainFilter, denyIncomplete"],
  "resources": ["Курс: Number(15,4)", "Кратность: Number(10,0)"]
}
```

### Batch — несколько объектов в одном файле

```json
[
  { "type": "Enum", "name": "Статусы", "values": ["Новый", "Закрыт"] },
  { "type": "Catalog", "name": "Валюты" },
  { "type": "Constant", "name": "ОсновнаяВалюта", "valueType": "CatalogRef.Валюты" }
]
```

