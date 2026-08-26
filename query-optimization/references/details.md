# Additional Details

Moved from query-optimization/SKILL.md to keep the skill lightweight.

## Temporary Tables

Use temporary tables to break complex queries into steps, avoid nested subqueries, and improve performance.

```
// Step 1: collect items into temp table
ВЫБРАТЬ Ссылка КАК Номенклатура
ПОМЕСТИТЬ ВТ_Товары
ИЗ Справочник.Номенклатура
ГДЕ Наименование ПОДОБНО &Маска
ИНДЕКСИРОВАТЬ ПО Номенклатура
;
// Step 2: get balances for those items
ВЫБРАТЬ
    Ост.Номенклатура КАК Номенклатура,
    Ост.КоличествоОстаток КАК Остаток
ИЗ РегистрНакопления.ОстаткиТоваров.Остатки(
        ,
        Номенклатура В (ВЫБРАТЬ Номенклатура ИЗ ВТ_Товары)
    ) КАК Ост
```

**Rules:**
- Separate queries in a batch with `;`
- `ПОМЕСТИТЬ <Name>` creates the temp table (place right after SELECT fields, before ИЗ)
- `ИНДЕКСИРОВАТЬ ПО <field>` — add after the query for temp tables with >1000 rows used in joins or `В` subqueries
- Minimize data volume and field count in temp tables
- **NEVER** create/drop temp tables in a loop
- Prefer temp tables over nested subqueries in JOIN conditions

## Parameters

Parameters are external values passed into the query. Syntax: `&ParameterName`.

```
ВЫБРАТЬ * ИЗ Справочник.Контрагенты ГДЕ Наименование ПОДОБНО &Маска
```

Passed via `execute_query` params: `{"Маска": "%Рога%"}`.

**Rules:**
- Always use parameters for external values — never concatenate strings into query text
- Enum values: use `ЗНАЧЕНИЕ()` in query text, not as parameter: `ГДЕ Тип = ЗНАЧЕНИЕ(Перечисление.ТипыЦен.Оптовая)`
- Date format in params: ISO 8601 (`"2024-01-15"` or `"2024-01-15T10:30:00"`)
- Boolean: `ИСТИНА` / `ЛОЖЬ` in query text, or pass `true`/`false` as parameter

## Comparing Reference Fields

When comparing reference fields (link-type attributes), **pass the reference as a parameter**:

```
// GOOD — reference passed as parameter from previous query result:
ВЫБРАТЬ * ИЗ Документ.ПродажаТоваров
ГДЕ Контрагент = &Контрагент
// params: {"Контрагент": {"_objectRef": true, "УникальныйИдентификатор": "...",
//                           "ТипОбъекта": "СправочникСсылка.Контрагенты", "Представление": "..."}}

// ALSO GOOD — compare via primitive attribute:
ГДЕ Контрагент.Наименование = "ООО Ромашка"
ГДЕ Контрагент.Код = "000001"

// AVOID — direct comparison with another table's reference:
ГДЕ Документ.Контрагент = Справочник.Контрагенты.Ссылка
```

**Rules:**
- **First choice:** pass reference object from previous query result as `&Parameter`
- **Fallback:** compare via primitive fields (Наименование, Код, etc.)
- Never compare reference fields directly from different sources

## Common Patterns

**1. Find by name (fuzzy):**
```
ВЫБРАТЬ Ссылка, Наименование ИЗ Справочник.Контрагенты ГДЕ Наименование ПОДОБНО &Маска
// params: {"Маска": "%рога%"}
```

**2. Latest N documents:**
```
ВЫБРАТЬ ПЕРВЫЕ 10 Ссылка, Дата, Номер, СуммаДокумента
ИЗ Документ.РеализацияТоваровУслуг
УПОРЯДОЧИТЬ ПО Дата УБЫВ
```

**3. Current balances (virtual table, no date = now):**
```
ВЫБРАТЬ Номенклатура, КоличествоОстаток
ИЗ РегистрНакопления.ОстаткиТоваров.Остатки(, Номенклатура = &Ном) КАК Ост
```

**4. Latest register slice:**
```
ВЫБРАТЬ Валюта, Курс ИЗ РегистрСведений.КурсыВалют.СрезПоследних(&Дата,) КАК Курсы
```

**5. Count by group:**
```
ВЫБРАТЬ Контрагент, КОЛИЧЕСТВО(*) КАК Кол
ИЗ Документ.РеализацияТоваровУслуг
СГРУППИРОВАТЬ ПО Контрагент
УПОРЯДОЧИТЬ ПО Кол УБЫВ
```

**6. Check existence:**
```
ВЫБРАТЬ ПЕРВЫЕ 1 Ссылка ИЗ Справочник.Контрагенты ГДЕ ИНН = &ИНН
```

**7. Exclude items marked for deletion:**
```
ГДЕ НЕ ПометкаУдаления
```

**8. Explore table structure (zero-row query with schema):**
```
ВЫБРАТЬ ПЕРВЫЕ 0 * ИЗ Справочник.Контрагенты
// use with include_schema: true in execute_query
```

## References

- [Query syntax reference](references/query-syntax-reference.md) — ВЫБОР (CASE), ОБЪЕДИНИТЬ, УПОРЯДОЧИТЬ ПО, ИТОГИ, ПОДОБНО patterns, ССЫЛКА, subqueries
- [Optimization and pitfalls](references/optimization-and-pitfalls.md) — index strategy, ИЛИ alternatives, compound types, virtual table rules, RLS impact
- [Functions and expressions](references/functions-and-expressions.md) — aggregate, date, string, type, math functions and type casting with ВЫРАЗИТЬ

