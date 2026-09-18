---
name: erf-init
description: Создать пустой внешний отчёт 1С (scaffold XML-исходников)
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# /erf-init — Создание нового отчёта

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/erf-init/scripts/init.py" -Name <Name> -Synonym <Synonym>
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/erf-init/scripts/init.ps1" -Name <Name> -Synonym <Synonym>
```
<!-- docs-evals:python-entrypoint:end -->

Генерирует минимальный набор XML-исходников для внешнего отчёта 1С: корневой файл метаданных и каталог отчёта.

## Usage

```
/erf-init <Name> [Synonym] [SrcDir] [--with-skd]
```

| Параметр  | Обязательный | По умолчанию | Описание                              |
|-----------|:------------:|--------------|---------------------------------------|
| Name      | да           | —            | Имя отчёта (латиница/кириллица)       |
| Synonym   | нет          | = Name       | Синоним (отображаемое имя)            |
| SrcDir    | нет          | `src`        | Каталог исходников относительно CWD   |
| --WithSKD | нет          | —            | Создать пустую СКД и привязать к MainDataCompositionSchema |

## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/erf-init/scripts/init.ps1 -Name "<Name>" [-Synonym "<Synonym>"] [-SrcDir "<SrcDir>"] [-WithSKD]
```

## Дальнейшие шаги

- Добавить форму: `/form-add`
- Добавить макет: `/template-add`
- Добавить справку: `/help-add`
- Собрать ERF: `epf-build` (канонический сборщик EPF/ERF)
