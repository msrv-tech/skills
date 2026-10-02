# Codex UI Test Fixtures

Отдельное расширение с тестовым окружением для нативной conformance-матрицы
CodexTestBridge. Оно не является частью Bridge и не требуется для его HTTP API,
UI worker или работы с прикладными конфигурациями.

В `src/` находятся только искусственные тестовые объекты: общая форма,
справочник, документ, перечисление, обработка, ПВХ, план счетов, ПВР,
бизнес-процесс, задача, подсистема и команда интерфейса. Тестовые данные
создаются идемпотентно при открытии формы `CodexUIConformance`.

Сборка на Linux:

```bash
IBCMD="$CODEX_IBCMD" ./scripts/build_cfe_linux.sh
```

Сборка на Windows:

```powershell
.\scripts\build_cfe_windows.ps1 -PlatformPath $env:CODEX_1C_PLATFORM
```

Статическая проверка покрытия действий Bridge:

```bash
python3 ./scripts/run_conformance.py --validate-only
```

Для реального прогона сначала установи `codex-test-bridge.cfe`, затем
`codex-ui-test-fixtures.cfe` отдельно в зарегистрированные тестовые базы с Bridge и запусти runner
с параметрами зарегистрированной базы. Не устанавливай fixture-CFE в рабочие
или демонстрационные базы, которые не предназначены для conformance-тестов.

Для серверной базы установка разрешена только через приватный реестр:

```bash
python3 ./scripts/install_from_test_database.py \
  --registry "$CODEX_1C_TEST_DATABASES" \
  --database <registered-test-database> \
  --platform "$CODEX_1C_EXECUTABLE"
```
