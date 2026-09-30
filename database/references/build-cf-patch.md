# build-cf-patch — Минимальный CF поверх бинарной основы

Используй этот режим, когда нужен CF только с явно разрешёнными изменениями
поверх production-конфигурации. Не собирай такой patch-CF через полную загрузку
XML: платформа может материализовать отсутствующие default-свойства форм и
создать ложные изменения метаданных.

## Входные данные

- `BaseCf` — неизменённый production CF, выгруженный той же версией платформы.
- `BaseConfigDir` — свежая полная XML-выгрузка, точно соответствующая `BaseCf`.
- `ConfigDir` — копия XML-исходников с требуемыми изменениями.
- `Files` или `ListFile` — точный allowlist относительных путей.
- `OutputFile` — итоговый CF.

Скрипт сначала проверяет, что XML-diff между `BaseConfigDir` и `ConfigDir`
точно совпадает с allowlist. Затем создаёт временную файловую ИБ, загружает в
неё `BaseCf` без `/UpdateDBCfg` и полной XML-выгрузкой доказывает, что бинарная
основа соответствует `BaseConfigDir`. После этого применяет только allowlist
через `-partial`, делает вторую полную контрольную XML-выгрузку и повторно
проверяет точный diff.
`ConfigDumpInfo.xml` исключается из сравнения и не может входить в allowlist.

Исходные XML не передаются платформе напрямую: `ConfigDir` копируется во
временный каталог, поэтому `-updateConfigDumpInfo` не меняет Git working tree.
CF сначала выгружается во временный файл и атомарно заменяет `OutputFile` только
после всех проверок. Staging-файл создаётся рядом с `OutputFile`, поэтому
атомарная замена не зависит от размещения системного temp на другом диске.
При лишнем или пропущенном изменении существующий итоговый CF остаётся
нетронутым. `OutputFile` и `ReportFile` должны находиться вне обоих каталогов
XML и не могут перезаписывать `BaseCf` или друг друга.

## Запуск

Linux:

```bash
python3 <skills-root>/database/scripts/build-cf-patch.py \
  -V8Path "$CODEX_1C_EXECUTABLE" \
  -BaseCf production.cf \
  -BaseConfigDir baseline-cfsrc \
  -ConfigDir cfsrc \
  -ListFile changed-files.txt \
  -OutputFile patch.cf \
  -ReportFile patch-report.json
```

Windows:

```powershell
powershell.exe -NoProfile -File <skills-root>/database/scripts/build-cf-patch.ps1 `
  -V8Path $env:CODEX_1C_EXECUTABLE `
  -BaseCf production.cf `
  -BaseConfigDir baseline-cfsrc `
  -ConfigDir cfsrc `
  -Files "CommonModules/Интеграция/Ext/Module.bsl" `
  -OutputFile patch.cf `
  -ReportFile patch-report.json
```

`ListFile` читается как UTF-8/UTF-8 BOM, один относительный путь на строку.
Нельзя одновременно указывать `Files` и `ListFile`; абсолютные пути,
`..`, дубликаты и `ConfigDumpInfo.xml` отклоняются.

## Условия остановки

Не создавай итоговый CF, если:

- бинарная основа и baseline XML получены разными версиями платформы;
- исходный XML-diff не совпадает с allowlist;
- контрольная выгрузка содержит дополнительные или пропущенные изменения;
- содержимое разрешённого файла после round-trip отличается от `ConfigDir`;
- платформа изменила исходные каталоги или не создала непустой CF.

Операция работает только с временной локальной ИБ и не требует подключения к
зарегистрированной тестовой базе.
