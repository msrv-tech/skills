# Additional Details

Moved from form-compile/SKILL.md to keep the skill lightweight.

## Автогенерация

- **Companion-элементы**: ContextMenu, ExtendedTooltip и др. создаются автоматически
- **Обработчики событий**: `"on": ["OnChange"]` → `ОрганизацияПриИзменении`
- **Namespace**: все 17 namespace-деклараций
- **ID**: последовательная нумерация, AutoCommandBar = id="-1"
- **Unknown keys**: выводится предупреждение о нераспознанных ключах

## Workflow

1. **Компиляция**: `/form-compile` генерирует `Form.xml` и автоматически регистрирует `<Form>` в `ChildObjects` родительского объекта (если OutputPath следует конвенции `.../TypePlural/ObjectName/Forms/FormName/Ext/Form.xml`).
2. **Метаданные формы** (`ФормаСписка.xml`) и `Module.bsl` создаёт `/form-add`. Если `/form-add` ещё не вызывался — вызови после `/form-compile`. Он не перезаписывает существующий Form.xml.
3. **Проверка**: `/form-validate`, `/form-info`.

## Верификация

```
/form-validate <OutputPath>    — проверка корректности XML
/form-info <OutputPath>        — визуальная сводка структуры
```

## Особенности для EDT-проектов

> **form-compile генерирует формы в формате logform (XML-выгрузка).** Для EDT-проектов форма будет работать, но дизайнер EDT может показать пустую форму из-за отсутствия EDT-специфичных свойств. Альтернативы: создать форму штатно через EDT или использовать MCP `generate_form_from_metadata` с `format="edt"`.

Если форма создается вручную или через form-compile для EDT, после генерации необходимо добавить:

### Критично (без этого дизайнер EDT пустой)

- `<extInfo xsi:type="form:ТипFormExtInfo"/>` на корневом `form:Form` - тип формы:
  - `CatalogFormExtInfo` - справочник
  - `DocumentFormExtInfo` - документ
  - `DataProcessorFormExtInfo` - обработка
  - `InformationRegisterFormExtInfo` - регистр сведений

### Обязательные свойства формы

- `commandInterface` с `<navigationPanel/>` и `<commandBar/>`
- `windowOpeningMode` = `LockOwnerWindow`
- `autoFillCheck` = `true`
- `showTitle`, `showCloseButton` = `true`
- `allowFormCustomize`, `saveWindowSettings` = `true`

### Обязательные свойства полей (InputField, LabelField, CheckBoxField)

- `visible`, `enabled` = `true`
- `userVisible` с `<common>true</common>`
- `editMode` = `EnterOnInput`
- `showInHeader`, `showInFooter` = `true`
- `typeDomainEnabled` = `true`
- `chooseType` = `true`
- `wrap` = `true`
- `textEdit` = `true`
- `headerHorizontalAlign` = `Left`

### Обязательные свойства кнопок (Button)

- Кнопка на форме (вне CommandBar): `type` = `UsualButton` (обязательно)
- Кнопка в CommandBar: `type` = `CommandBarButton` (дефолт, можно не указывать)
- Имя кнопки = имя команды (не `Кнопка[Команда]`, не `[Команда]Кнопка`)

### Размещение обработчиков событий (Events)

Обработчики InputField делятся по месту размещения в XML:

**На уровне элемента** (`<Events>` внутри `<InputField>`):
- `OnChange`, `DragCheck`, `Drag`, `DragStart`

**Внутри `<extInfo xsi:type="form:InputFieldExtInfo">`** (`<handlers>`):
- `StartChoice`, `Clearing`, `Opening`, `ChoiceProcessing`, `AutoComplete`, `TextEditEnd`

Эти события специфичны для типа поля и размещаются внутри extInfo, а не на уровне элемента.

### Специфика объектов

- Иерархический справочник - всегда добавлять поле Родитель (Parent)
- DynamicList: `<extInfo xsi:type="form:DynamicListExtInfo">` на атрибуте с `mainTable`

## Особенности для внешних обработок (EPF)

- **Тип главного реквизита**: `ExternalDataProcessorObject.ИмяОбработки` (не `DataProcessorObject`)
- **DataPath**: используйте реквизиты формы (`ИмяРеквизита`), а не `Объект.ИмяРеквизита` — у внешних обработок нет реквизитов объекта в метаданных
- **Ссылочные типы**: `CatalogRef.XXX`, `DocumentRef.XXX` допустимы в XML, но для сборки EPF потребуется база с целевой конфигурацией (см. `/epf-build`)

