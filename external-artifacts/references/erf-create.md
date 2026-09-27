# erf-create — Создание нового отчёта

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/external-artifacts/scripts/erf-create.py" -Name <Name> -Synonym <Synonym>
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/external-artifacts/scripts/erf-create.ps1" -Name <Name> -Synonym <Synonym>
```
<!-- docs-evals:python-entrypoint:end -->

Генерирует минимальный набор XML-исходников для внешнего отчёта 1С: корневой файл метаданных и каталог отчёта.

## Usage

```
/external-artifacts:erf-create <Name> [Synonym] [SrcDir] [--with-skd]
```

| Параметр  | Обязательный | По умолчанию | Описание                              |
|-----------|:------------:|--------------|---------------------------------------|
| Name      | да           | —            | Имя отчёта (латиница/кириллица)       |
| Synonym   | нет          | = Name       | Синоним (отображаемое имя)            |
| SrcDir    | нет          | `src`        | Каталог исходников относительно CWD   |
| --WithSKD | нет          | —            | Создать пустую СКД и привязать к MainDataCompositionSchema |

## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/external-artifacts/scripts/erf-create.ps1 -Name "<Name>" [-Synonym "<Synonym>"] [-SrcDir "<SrcDir>"] [-WithSKD]
```

## Дальнейшие шаги

- Добавить форму: `/forms:add`
- Добавить макет: `/layouts:attach`
- Добавить справку: `/metadata:add-help`
- Собрать ERF: `external-artifacts:build` (канонический сборщик EPF/ERF)
