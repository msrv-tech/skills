# Развёртывание Codex Test Bridge

Запускать из клона репозитория. Реестр выбирается штатным resolver навыка
`test-databases`; реальные подключения хранить только в приватном реестре.

Для каждой цели требуются `Srvr`, `Ref`, `User`, `Password`,
`Bridge.BaseUrl` и `BridgeCompatibilityMode` (либо `path` к исходникам
с `Configuration.xml`). `Srvr` — сервер 1С, а не адрес веб-публикации;
`Ref` должен быть подтверждён как имя серверной ИБ.
HTTP-сервис `codex-test` должен быть разрешён в VRD на сервере публикации
инструментом `codex-test-bridge/scripts/enable_vrd_linux.py`.
Если запись содержит `WebPublication` (`SshHost`, `Container`, `VrdPath`),
скрипт через SSH и `pct exec` сохраняет копию VRD, включает Bridge, проверяет
Apache и перезагружает его настройки.

```bash
python3 scripts/deploy_test_bridge.py --sync-only
python3 scripts/deploy_test_bridge.py --refresh-compatibility --dry-run
python3 scripts/deploy_test_bridge.py --dry-run
python3 scripts/deploy_test_bridge.py --platform /path/to/1cv8
```

По умолчанию цели — `unf1` и `bp1`. Выбор: повторяемый `--database`.
Linux Designer требует Xvfb и зависимостей штатного установщика;
версия клиента должна соответствовать серверу 1С.
Одна команда используется для первой установки и последующего обновления.
Установщик загружает CFE и обновляет конфигурацию базы. После установки
проверяются GET/POST health, версия Bridge и отсутствие bootstrap-пользователей.
Перед изменением баз обновляются 13 локальных навыков Codex и `common`.
Сбой останавливает развёртывание; автоматического отката нет.

`--refresh-compatibility` читает корневые метаданные через скрытый Designer и
обновляет режимы в приватном реестре; вместе с `--dry-run` базы не изменяются.
Без этого флага `--dry-run` не меняет и локальные файлы. Клиент автоматически
выбирается из `/opt/1cv8/x86_64` по `Designer.PlatformVersion`, если кандидат один.
После подготовки реестра запуск: `python3 scripts/deploy_test_bridge.py`.

Проверка установленных расширений без изменения баз и скиллов:
`python3 scripts/deploy_test_bridge.py --verify-only`.
