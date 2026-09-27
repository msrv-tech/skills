# add — Добавление формы к объекту конфигурации

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/forms/scripts/add.py" -ObjectPath <project-root>/src/Object.xml
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/forms/scripts/add.ps1" -ObjectPath <project-root>/src/Object.xml
```
<!-- docs-evals:python-entrypoint:end -->

Создаёт управляемую форму (metadata XML + Form.xml + Module.bsl) и регистрирует её в корневом XML объекта конфигурации (Document, Catalog, InformationRegister и др.).

## Usage

```
/forms:add <ObjectPath> <FormName> [Purpose] [Synonym] [--set-default]
```

| Параметр    | Обязательный | По умолчанию | Описание                                     |
|-------------|:------------:|--------------|----------------------------------------------|
| ObjectPath  | да           | —            | Путь к XML-файлу объекта (Documents/Док.xml)  |
| FormName    | да           | —            | Имя формы (ФормаДокумента)                    |
| Purpose     | нет          | Object       | Назначение: Object, List, Choice, Record      |
| Synonym     | нет          | = FormName   | Синоним формы                                 |
| --set-default | нет        | авто         | Установить как форму по умолчанию             |

## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/forms/scripts/add.ps1 -ObjectPath "<ObjectPath>" -FormName "<FormName>" [-Purpose "<Purpose>"] [-Synonym "<Synonym>"] [-SetDefault]
```

## Purpose — назначение формы

| Purpose | Допустимые типы объектов | Основной реквизит | DefaultForm-свойство |
|---------|-------------------------|-------------------|---------------------|
| Object  | Document, Catalog, DataProcessor, Report, ExternalDataProcessor, ExternalReport, ChartOf*, ExchangePlan, BusinessProcess, Task | Объект (тип: *Object.Имя) | DefaultObjectForm (DefaultForm для DataProcessor/Report/ExternalDataProcessor/ExternalReport) |
| List    | Все кроме DataProcessor | Список (DynamicList) | DefaultListForm |
| Choice  | Document, Catalog, ChartOf*, ExchangePlan, BusinessProcess, Task | Список (DynamicList) | DefaultChoiceForm |
| Record  | InformationRegister | Запись (InformationRegisterRecordManager) | DefaultRecordForm |

## Примеры

```
# Форма документа
/forms:add Documents/АвансовыйОтчет.xml ФормаДокумента --purpose Object

# Форма списка каталога
/forms:add Catalogs/Контрагенты.xml ФормаСписка --purpose List

# Форма записи регистра сведений
/forms:add InformationRegisters/КурсыВалют.xml ФормаЗаписи --purpose Record

# Форма выбора с синонимом
/forms:add Catalogs/Номенклатура.xml ФормаВыбора --purpose Choice --synonym "Выбор номенклатуры"

# Установить как форму по умолчанию
/forms:add Documents/Заказ.xml ФормаДокументаНовая --purpose Object --set-default
```

## Workflow

1. `/forms:add` — создать каркас формы
2. `/forms:create` — сформировать наполненный Form.xml из полного определения
3. `/forms:validate` — проверить корректность
4. `/forms:inspect` — проанализировать результат
