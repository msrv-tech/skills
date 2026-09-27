# Skills Catalog

Репозиторий состоит из 13 самодостаточных доменных skills. Режимы, инструкции и
точки входа перечислены в [`skill-domains.json`](skill-domains.json).

| # | Skill | Назначение | Режимы |
|---:|---|---|---|
| 1 | `configuration` | Конфигурации 1С | `configuration:create-empty`, `configuration:create-project`, `configuration:add-object`, `configuration:inspect`, `configuration:edit`, `configuration:validate` |
| 2 | `extension` | Расширения CFE | `extension:create`, `extension:full-cycle`, `extension:borrow`, `extension:patch-method`, `extension:inspect`, `extension:validate` |
| 3 | `metadata` | Объекты метаданных и справка | `metadata:create`, `metadata:inspect`, `metadata:edit`, `metadata:remove`, `metadata:validate`, `metadata:add-help` |
| 4 | `forms` | Управляемые формы | `forms:add`, `forms:create`, `forms:inspect`, `forms:edit`, `forms:remove`, `forms:validate`, `forms:patterns` |
| 5 | `layouts` | Макеты и MXL | `layouts:mxl-create`, `layouts:mxl-decompile`, `layouts:mxl-inspect`, `layouts:mxl-validate`, `layouts:attach`, `layouts:remove` |
| 6 | `reports` | СКД и запросы | `reports:skd-create`, `reports:skd-decompile`, `reports:skd-inspect`, `reports:skd-edit`, `reports:skd-validate`, `reports:query` |
| 7 | `access-and-navigation` | Роли, подсистемы, интерфейс | `role-create`, `role-inspect`, `role-validate`, `subsystem-create`, `subsystem-inspect`, `subsystem-edit`, `subsystem-validate`, `interface-edit`, `interface-validate` |
| 8 | `external-artifacts` | EPF, ERF и БСП | `epf-create`, `epf-full-cycle`, `erf-create`, `build`, `dump`, `validate`, `bsp-register`, `bsp-command` |
| 9 | `database` | Информационные базы и ibcmd | `create`, `project-settings`, `run`, `update`, `load-xml`, `dump-xml`, `load-cf`, `dump-cf`, `load-git`, `repository-update`, `ibcmd` |
| 10 | `web-publication` | Apache и публикации | `web-publication:publish`, `web-publication:inspect`, `web-publication:unpublish`, `web-publication:stop` |
| 11 | `ui-testing` | Web UI и Playwright | `ui-testing:session`, `ui-testing:test`, `ui-testing:scaffold` |
| 12 | `codex-test-bridge` | HTTP API и нативный UI TestClient/TestManager | самостоятельный продуктовый блок |
| 13 | `test-databases` | Реестр разрешённых тестовых ИБ | самостоятельный защищённый блок |

## Контракт маршрутизации

1. Агент выбирает один из 13 skills.
2. Доменный `SKILL.md` определяет режим по намерению пользователя.
3. Перед действием агент полностью читает соответствующий файл в `references/`.
4. Скрипты запускаются из `<domain>/scripts/`; старые CLI-пути не поддерживаются.
5. Для любой существующей информационной базы дополнительно применяется
   `test-databases`.

Отдельных маршрутизаторов и каталогов операций нет: анализ, изменение и
проверка являются режимами соответствующего предметного блока.
