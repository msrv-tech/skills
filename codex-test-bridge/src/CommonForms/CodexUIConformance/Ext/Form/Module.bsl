&НаСервере
Процедура OnCreateAtServer(Отказ, СтандартнаяОбработка)
	ИнициализироватьСостояние();
	Элементы.DropdownValue.СписокВыбора.Добавить("Alpha");
	Элементы.DropdownValue.СписокВыбора.Добавить("Beta");
	Элементы.DropdownValue.СписокВыбора.Добавить("Gamma");
КонецПроцедуры

&НаКлиенте
Процедура TreeRowsOnActivateRow(Элемент)
	ТекущиеДанные = Элемент.ТекущиеДанные;
	Если ТекущиеДанные <> Неопределено Тогда
		Status = ТекущиеДанные.Key;
	КонецЕсли;
КонецПроцедуры

&НаСервере
Процедура ИнициализироватьСостояние()
	TextValue = "initial";
	MultilineValue = "line one" + Символы.ПС + "line two";
	NumberValue = 10;
	DateValue = Дата(2026, 1, 2);
	DropdownValue = "Alpha";
	FlagValue = Ложь;
	ReadOnlyValue = "read-only";
	DisabledValue = "disabled";
	Status = "ready";
	ClickCount = 0;
	GroupValue = "inside group";
	TextDocumentValue = Новый ТекстовыйДокумент;
	TextDocumentValue.УстановитьТекст("fixture text document");
	FormattedDocumentValue = Новый ФорматированныйДокумент;
	SpreadsheetDocumentValue = Новый ТабличныйДокумент;
	SpreadsheetDocumentValue.Область("R1C1").Текст = "fixture spreadsheet document";
	Rows.Очистить();
	ДобавитьСтроку("row-1", "Alpha row", 10);
	ДобавитьСтроку("row-2", "Beta row", 20);
	ДобавитьСтроку("row-3", "Gamma row", 30);
	ИнициализироватьДеревоFixture();
	ИнициализироватьСсылочныеЗначения();
КонецПроцедуры

&НаСервере
Процедура ИнициализироватьДеревоFixture()
	Дерево = Новый ДеревоЗначений;
	Дерево.Колонки.Добавить("Key");
	Дерево.Колонки.Добавить("Text");
	Корень = Дерево.Строки.Добавить();
	Корень.Key = "tree-parent";
	Корень.Text = "Fixture tree parent";
	Потомок = Корень.Строки.Добавить();
	Потомок.Key = "tree-child";
	Потомок.Text = "Fixture tree child";
	ЗначениеВРеквизитФормы(Дерево, "TreeRows");
КонецПроцедуры

&НаСервере
Процедура ИнициализироватьСсылочныеЗначения()
	Ссылки = ОбеспечитьСсылочныеДанныеFixture();
	CatalogValue = Справочники.CodexUIFixtureCatalog.ПустаяСсылка();
	CatalogChoiceValue = Справочники.CodexUIFixtureCatalog.ПустаяСсылка();
	DocumentValue = Документы.CodexUIFixtureDocument.ПустаяСсылка();
	CharacteristicValue = ПланыВидовХарактеристик.CodexUIFixtureCharacteristics.ПустаяСсылка();
	AccountValue = ПланыСчетов.CodexUIFixtureAccounts.ПустаяСсылка();
	CalculationTypeValue = ПланыВидовРасчета.CodexUIFixtureCalculationTypes.ПустаяСсылка();
	EnumValue = Перечисления.CodexUIFixtureStatus.Draft;
	CompositeValue = Справочники.CodexUIFixtureCatalog.ПустаяСсылка();

	ЗаполнитьСписокВыбораСсылки(Элементы.CatalogValue.СписокВыбора, Ссылки.Catalog, "Fixture catalog Alpha");
	ЗаполнитьСписокВыбораСсылки(Элементы.DocumentValue.СписокВыбора, Ссылки.Document, "Fixture document Alpha");
	ЗаполнитьСписокВыбораСсылки(Элементы.CharacteristicValue.СписокВыбора, Ссылки.Characteristic, "Fixture characteristic Alpha");
	ЗаполнитьСписокВыбораСсылки(Элементы.AccountValue.СписокВыбора, Ссылки.Account, "Fixture account Alpha");
	ЗаполнитьСписокВыбораСсылки(Элементы.CalculationTypeValue.СписокВыбора, Ссылки.CalculationType, "Fixture calculation type Alpha");
	Элементы.CompositeValue.СписокВыбора.Очистить();
	Элементы.CompositeValue.СписокВыбора.Добавить(Ссылки.Catalog, "Fixture catalog Alpha");
	Элементы.CompositeValue.СписокВыбора.Добавить(Ссылки.Document, "Fixture document Alpha");
	Элементы.CompositeValue.СписокВыбора.Добавить(Ссылки.Characteristic, "Fixture characteristic Alpha");

	ReferenceRows.Очистить();
	СтрокаСсылок = ReferenceRows.Добавить();
	СтрокаСсылок.Key = "reference-row-1";
	ЗаполнитьСписокВыбораСсылки(Элементы.ReferenceRowsCatalogValue.СписокВыбора, Ссылки.Catalog, "Fixture catalog Alpha");
	ЗаполнитьСписокВыбораСсылки(Элементы.ReferenceRowsDocumentValue.СписокВыбора, Ссылки.Document, "Fixture document Alpha");
	ЗаполнитьСписокВыбораСсылки(Элементы.ReferenceRowsCharacteristicValue.СписокВыбора, Ссылки.Characteristic, "Fixture characteristic Alpha");
КонецПроцедуры

&НаСервере
Процедура ЗаполнитьСписокВыбораСсылки(СписокВыбора, Ссылка, Представление)
	СписокВыбора.Очистить();
	СписокВыбора.Добавить(Ссылка, Представление);
КонецПроцедуры

&НаСервере
Функция ОбеспечитьСсылочныеДанныеFixture()
	CatalogFolder = НайтиСсылкуFixture("Справочник.CodexUIFixtureCatalog", "Код", "CTB-UI-FOLDER");
	Если CatalogFolder = Неопределено Тогда
		Объект = Справочники.CodexUIFixtureCatalog.СоздатьГруппу();
		Объект.Код = "CTB-UI-FOLDER";
		Объект.Наименование = "Fixture folder";
		Объект.Записать();
		CatalogFolder = Объект.Ссылка;
	КонецЕсли;

	Catalog = НайтиСсылкуFixture("Справочник.CodexUIFixtureCatalog", "Код", "CTB-UI-CATALOG");
	Если Catalog = Неопределено Тогда
		Объект = Справочники.CodexUIFixtureCatalog.СоздатьЭлемент();
		Объект.Код = "CTB-UI-CATALOG";
		Объект.Наименование = "Fixture catalog Alpha";
		Объект.Enabled = Истина;
		Объект.FixtureStatus = Перечисления.CodexUIFixtureStatus.Ready;
		Объект.Записать();
		Catalog = Объект.Ссылка;
	ИначеЕсли ЗначениеЗаполнено(Catalog.Родитель) Тогда
		Объект = Catalog.ПолучитьОбъект();
		Объект.Родитель = Справочники.CodexUIFixtureCatalog.ПустаяСсылка();
		Объект.Записать();
		Catalog = Объект.Ссылка;
	КонецЕсли;
	TreeChild = НайтиСсылкуFixture("Справочник.CodexUIFixtureCatalog", "Код", "CTB-UI-TREE-CHILD");
	Если TreeChild = Неопределено Тогда
		Объект = Справочники.CodexUIFixtureCatalog.СоздатьЭлемент();
		Объект.Код = "CTB-UI-TREE-CHILD";
		Объект.Наименование = "Fixture tree child";
		Объект.Enabled = Истина;
		Объект.FixtureStatus = Перечисления.CodexUIFixtureStatus.Ready;
		Объект.Родитель = CatalogFolder;
		Объект.Записать();
	ИначеЕсли TreeChild.Родитель <> CatalogFolder Тогда
		Объект = TreeChild.ПолучитьОбъект();
		Объект.Родитель = CatalogFolder;
		Объект.Записать();
	КонецЕсли;

	Characteristic = НайтиСсылкуFixture("ПланВидовХарактеристик.CodexUIFixtureCharacteristics", "Код", "CTB-UI-CHAR");
	Если Characteristic = Неопределено Тогда
		Объект = ПланыВидовХарактеристик.CodexUIFixtureCharacteristics.СоздатьЭлемент();
		Объект.Код = "CTB-UI-CHAR";
		Объект.Наименование = "Fixture characteristic Alpha";
		Объект.ТипЗначения = Новый ОписаниеТипов("Строка");
		Объект.Записать();
		Characteristic = Объект.Ссылка;
	КонецЕсли;

	Account = НайтиСсылкуFixture("ПланСчетов.CodexUIFixtureAccounts", "Код", "CTB-UI-ACCOUNT");
	Если Account = Неопределено Тогда
		Объект = ПланыСчетов.CodexUIFixtureAccounts.СоздатьСчет();
		Объект.Код = "CTB-UI-ACCOUNT";
		Объект.Наименование = "Fixture account Alpha";
		Объект.Active = Истина;
		Объект.Записать();
		Account = Объект.Ссылка;
	КонецЕсли;

	CalculationType = НайтиСсылкуFixture("ПланВидовРасчета.CodexUIFixtureCalculationTypes", "Код", "CTB-UI-CALC");
	Если CalculationType = Неопределено Тогда
		Объект = ПланыВидовРасчета.CodexUIFixtureCalculationTypes.СоздатьВидРасчета();
		Объект.Код = "CTB-UI-CALC";
		Объект.Наименование = "Fixture calculation type Alpha";
		Объект.Записать();
		CalculationType = Объект.Ссылка;
	КонецЕсли;

	Document = НайтиСсылкуFixture("Документ.CodexUIFixtureDocument", "Номер", "CTB-UI-DOCUMENT");
	Если Document = Неопределено Тогда
		Объект = Документы.CodexUIFixtureDocument.СоздатьДокумент();
		Объект.Номер = "CTB-UI-DOCUMENT";
		Объект.Дата = Дата(2026, 1, 2, 12, 0, 0);
		Объект.CatalogValue = Catalog;
		Объект.CharacteristicValue = Characteristic;
		Объект.AccountValue = Account;
		Объект.CalculationTypeValue = CalculationType;
		Объект.FixtureStatus = Перечисления.CodexUIFixtureStatus.Ready;
		СтрокаДокумента = Объект.References.Добавить();
		СтрокаДокумента.CatalogValue = Catalog;
		СтрокаДокумента.CharacteristicValue = Characteristic;
		Объект.Записать();
		Document = Объект.Ссылка;
	КонецЕсли;

	СсылкаСправочникаUUID = Справочники.CodexUIFixtureCatalog.ПолучитьСсылку(
		Новый УникальныйИдентификатор("22222222-2222-4222-8222-222222222222"));
	Если Не СсылкаСуществуетFixture("Справочник.CodexUIFixtureCatalog", СсылкаСправочникаUUID) Тогда
		Объект = Справочники.CodexUIFixtureCatalog.СоздатьЭлемент();
		Объект.УстановитьСсылкуНового(СсылкаСправочникаUUID);
		Объект.Код = "CTB-UI-CATALOG-UUID";
		Объект.Наименование = "Fixture catalog UUID";
		Объект.Enabled = Истина;
		Объект.FixtureStatus = Перечисления.CodexUIFixtureStatus.Ready;
		Объект.Записать();
	КонецЕсли;

	СсылкаДокументаUUID = Документы.CodexUIFixtureDocument.ПолучитьСсылку(
		Новый УникальныйИдентификатор("33333333-3333-4333-8333-333333333333"));
	Если Не СсылкаСуществуетFixture("Документ.CodexUIFixtureDocument", СсылкаДокументаUUID) Тогда
		Объект = Документы.CodexUIFixtureDocument.СоздатьДокумент();
		Объект.УстановитьСсылкуНового(СсылкаДокументаUUID);
		Объект.Номер = "CTB-UI-DOCUMENT-UUID";
		Объект.Дата = Дата(2026, 1, 3, 12, 0, 0);
		Объект.CatalogValue = Catalog;
		Объект.CharacteristicValue = Characteristic;
		Объект.AccountValue = Account;
		Объект.CalculationTypeValue = CalculationType;
		Объект.FixtureStatus = Перечисления.CodexUIFixtureStatus.Ready;
		Объект.Записать();
	КонецЕсли;

	Возврат Новый Структура("Catalog,Document,Characteristic,Account,CalculationType", Catalog, Document, Characteristic, Account, CalculationType);
КонецФункции

&НаСервере
Функция СсылкаСуществуетFixture(ИмяТаблицы, Ссылка)
	Запрос = Новый Запрос("ВЫБРАТЬ ПЕРВЫЕ 1 Ссылка ИЗ " + ИмяТаблицы + " ГДЕ Ссылка = &Ссылка");
	Запрос.УстановитьПараметр("Ссылка", Ссылка);
	Возврат Не Запрос.Выполнить().Пустой();
КонецФункции

&НаСервере
Функция НайтиСсылкуFixture(ИмяТаблицы, ИмяПоля, Значение)
	Запрос = Новый Запрос;
	Запрос.Текст = "ВЫБРАТЬ ПЕРВЫЕ 1 Ссылка ИЗ " + ИмяТаблицы + " ГДЕ " + ИмяПоля + " = &Значение";
	Запрос.УстановитьПараметр("Значение", Значение);
	Выборка = Запрос.Выполнить().Выбрать();
	Если Выборка.Следующий() Тогда
		Возврат Выборка.Ссылка;
	КонецЕсли;
	Возврат Неопределено;
КонецФункции

&НаСервере
Процедура ДобавитьСтроку(Ключ, Текст, Число)
	НоваяСтрока = Rows.Добавить();
	НоваяСтрока.Key = Ключ;
	НоваяСтрока.Text = Текст;
	НоваяСтрока.Number = Число;
КонецПроцедуры

&НаКлиенте
Процедура IncrementCommand(Команда)
	ClickCount = ClickCount + 1;
	Status = "button:" + Формат(ClickCount, "ЧГ=0");
КонецПроцедуры

&НаКлиенте
Процедура ResetCommand(Команда)
	ИнициализироватьСостояниеНаСервере();
КонецПроцедуры

&НаСервере
Процедура ИнициализироватьСостояниеНаСервере()
	ИнициализироватьСостояние();
КонецПроцедуры

&НаКлиенте
Процедура ShowDialogCommand(Команда)
	Оповещение = Новый ОписаниеОповещения("ПослеЗакрытияДиалога", ЭтотОбъект);
	ПоказатьПредупреждение(Оповещение, "Codex conformance dialog");
КонецПроцедуры

&НаКлиенте
Процедура ПослеЗакрытияДиалога(ДополнительныеПараметры) Экспорт
	Status = "dialog:closed";
КонецПроцедуры

&НаКлиенте
Процедура TextValueПриИзменении(Элемент)
	Status = "text:" + TextValue;
КонецПроцедуры

&НаКлиенте
Процедура MultilineValueПриИзменении(Элемент)
	Status = "multiline:changed";
КонецПроцедуры

&НаКлиенте
Процедура NumberValueПриИзменении(Элемент)
	Status = "number:changed";
КонецПроцедуры

&НаКлиенте
Процедура DateValueПриИзменении(Элемент)
	Status = "date:changed";
КонецПроцедуры

&НаКлиенте
Процедура DropdownValueПриИзменении(Элемент)
	Status = "dropdown:" + DropdownValue;
КонецПроцедуры

&НаКлиенте
Процедура FlagValueПриИзменении(Элемент)
	Status = ?(FlagValue, "flag:true", "flag:false");
КонецПроцедуры

&НаКлиенте
Процедура RowsTextПриИзменении(Элемент)
	Status = "table:text-changed";
КонецПроцедуры

&НаКлиенте
Процедура RowsNumberПриИзменении(Элемент)
	Status = "table:number-changed";
КонецПроцедуры

&НаКлиенте
Процедура ReferenceValueПриИзменении(Элемент)
	Status = "reference:changed";
КонецПроцедуры

&НаКлиенте
Процедура ClickableDecorationНажатие(Элемент, СтандартнаяОбработка)
	СтандартнаяОбработка = Ложь;
	Status = "decoration:clicked";
КонецПроцедуры
