# reports:skd-decompile — JSON-черновик из Template.xml СКД

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/reports/scripts/skd-decompile.py" -TemplatePath <project-root>/Template.xml
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/reports/scripts/skd-decompile.ps1" -TemplatePath <project-root>/Template.xml
```
<!-- docs-evals:python-entrypoint:end -->

Читает Template.xml и эмитит JSON в формате `reports:skd-create`. **Результат — черновик**, а не обратимое представление: см. раздел «Что получаешь».

## Когда использовать

- **Scaffold нового отчёта по образцу** — взять существующий СКД, получить JSON, поправить и скомпилировать в новый.
- **Структурный рефакторинг** — переписать вариант, перерисовать шаблон, перебрать набор полей.

## Когда **не** использовать

- **Точечные правки готового отчёта** (добавить поле, фильтр, итог, переименовать) → `/reports:skd-edit`. Цикл «декомпиляция → правка JSON → компиляция» переписывает шаблон целиком, может терять непокрытые конструкции и даёт большой diff в исходниках. `/reports:skd-edit` правит адресно, без полной реконструкции.

## Параметры

| Параметр | Описание |
|----------|----------|
| `TemplatePath` | Путь к Template.xml (обязательный) |
| `OutputPath` | Путь к выходному JSON. Если не задан — JSON в stdout |

```powershell
powershell.exe -NoProfile -File "${CLAUDE_SKILL_DIR}/scripts/skd-decompile.ps1" -TemplatePath "<Template.xml>" -OutputPath "<out.json>"
```

## Что получаешь

JSON-черновик в формате `/reports:skd-create` — **не полное обратимое представление СКД**. На вход компилятору такой JSON напрямую может не пойти: в нём встречаются sentinel-узлы (маркер `__unsupported__`).

- **Готовые узлы** — большая часть СКД (поля, параметры, шаблоны, варианты со structure/filter/order/conditionalAppearance и т.п.) ложится в JSON как обычные узлы DSL.
- **Sentinel-узлы** — места, где встретилась конструкция, которую декомпилятор не умеет выразить в DSL. JSON остаётся валидным, но компилятор откажется его собирать, пока sentinel не **заменён ручной реализацией** (явный raw `template`, прописанный appearance и т.п.) **или не удалён**, если в новом отчёте конструкция не нужна. Это намеренный барьер — чтобы непокрытое не уехало в финальный отчёт незамеченным.
- **`<basename>.warnings.md`** рядом с `OutputPath` — список всех sentinel-узлов с координатами в исходнике, по нему удобно обходить места под ручную доработку.
- **Критичные конструкции** (Picture cells, ХранилищеЗначения, вложенные схемы, не-СКД root) — скрипт падает с ненулевым кодом и сообщением в stderr; такой Template как образец не годится.

## Workflow

1. `/reports:skd-decompile <Template.xml> -OutputPath draft.json` — получить черновик.
2. Открыть `draft.warnings.md`, посмотреть, что не покрылось.
3. Поправить JSON под задачу. Sentinel-узлы — заменить на ручную реализацию (через явный raw `template`, через ручное описание appearance и т.п.) либо удалить, если конструкция в новом отчёте не нужна.
4. `/reports:skd-create -DefinitionFile draft.json -OutputPath new-Template.xml` — собрать обратно.
5. `/reports:skd-validate` + `/reports:skd-inspect` — проверить.
