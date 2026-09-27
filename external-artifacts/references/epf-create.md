# epf-create — Создание новой обработки

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/external-artifacts/scripts/epf-create.py" -Name <Name> -Synonym <Synonym>
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/external-artifacts/scripts/epf-create.ps1" -Name <Name> -Synonym <Synonym>
```
<!-- docs-evals:python-entrypoint:end -->

Генерирует минимальный набор XML-исходников для внешней обработки 1С: корневой файл метаданных и каталог обработки.

## Usage

```
/external-artifacts:epf-create <Name> [Synonym] [SrcDir]
```

| Параметр  | Обязательный | По умолчанию | Описание                            |
|-----------|:------------:|--------------|-------------------------------------|
| Name      | да           | —            | Имя обработки (латиница/кириллица)  |
| Synonym   | нет          | = Name       | Синоним (отображаемое имя)          |
| SrcDir    | нет          | `src`        | Каталог исходников относительно CWD |

## Команда

```powershell
powershell.exe -NoProfile -File <skills-root>/external-artifacts/scripts/epf-create.ps1 -Name "<Name>" [-Synonym "<Synonym>"] [-SrcDir "<SrcDir>"]
```

## Дальнейшие шаги

- Добавить форму: `forms:add`
- Добавить макет: `/layouts:attach`
- Добавить справку: `/metadata:add-help`
- Собрать EPF: `/external-artifacts:build`
