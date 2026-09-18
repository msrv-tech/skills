---
name: web-publish
description: Публикация информационной базы 1С через Apache. Используй когда пользователь просит опубликовать базу, сервисы, настроить веб-доступ, веб-клиент, открыть в браузере
allowed-tools:
  - Bash
  - Read
  - Glob
  - AskUserQuestion
---

# /web-publish — Публикация 1С через Apache

<!-- docs-evals:python-entrypoint:start -->
## Запуск скрипта

Основной запуск на Linux выполняется Python 3 с аргументами CLI скрипта:

```bash
python3 "<skills-root>/web-publish/scripts/web-publish.py" -InfoBasePath <test-infobase-path> -AppName <publication-name>
```

Windows PowerShell остаётся отдельным вариантом запуска:

```powershell
powershell.exe -NoProfile -File "<skills-root>/web-publish/scripts/web-publish.ps1" -InfoBasePath <test-infobase-path> -AppName <publication-name>
```
<!-- docs-evals:python-entrypoint:end -->

Генерирует `default.vrd`, настраивает `httpd.conf` и запускает Apache HTTP Server для веб-доступа к информационной базе. При необходимости скачивает portable Apache. Идемпотентный — повторный вызов обновляет конфигурацию.

## Usage

```
/web-publish [database]
/web-publish dev
/web-publish dev --manual
/web-publish dev --port 9090
```

## Параметры подключения

Перед обращением к ИБ обязательно примени `test-databases`: на Linux запусти `python3 <skills-root>/test-databases/scripts/resolve-registry.py`, а на Windows — `resolve-registry.ps1` через PowerShell; затем выбери разрешённую запись по его правилам. Параметры подключения, пользователя и пароль передавай только из выбранной записи.

Не принимай произвольный путь, сервер или строку подключения как замену реестру. `.v8-project.json` разрешён только для вспомогательных полей вроде `v8path`, `configSrc` или `webUrl`. Если подходящей записи нет или выбор неоднозначен, остановись и запроси уточнение.
## Команда

Ubuntu с системным Apache:

```bash
python3 <skills-root>/web-publish/scripts/web-publish.py \
  -InfoBasePath /srv/1c/mydb -AppName mydb
```

Linux использует официальный `wsap24.so` из `-WsModule`, `-V8Path`,
`ONEC_WSAP_MODULE_PATH` или стандартного каталога `/opt/1cv8/x86_64`.
Создаются только отдельные файлы `1c-skills-*.conf` в
`/etc/apache2/conf-available` и ссылки в `conf-enabled`. Перед каждым reload
обязательно выполняется `apache2ctl configtest`; при ошибке изменения
откатываются. Скрипт не вызывает `sudo`, не скачивает компоненты и не изменяет
чужие публикации.

Для первичной установки передай локальный официальный WS DEB либо
`setup-full-*.run` с той же полной версией платформы и архитектурой `amd64`.
Установщик проверяет версию и после установки требует matching `webinst` и
`wsap24.so`:

```bash
sudo <skills-root>/web-publish/scripts/install_ubuntu.sh \
  --ws-deb /path/to/1c-enterprise-ws.deb --platform-version 8.3.27.1688

# Вариант для официального полного installer:
sudo <skills-root>/web-publish/scripts/install_ubuntu.sh \
  --installer-run /path/to/setup-full-8.5.1.1529-x86_64.run \
  --platform-version 8.5.1.1529
```

Без одного из `--ws-deb`/`--installer-run` установщик завершается с ошибкой.
Агент не должен запускать установщик или `sudo` без отдельного запроса
пользователя.

Windows:

```powershell
powershell.exe -NoProfile -File <skills-root>/web-publish/scripts/web-publish.ps1 <параметры>
```

### Параметры скрипта

| Параметр | Обязательный | Описание |
|----------|:------------:|----------|
| `-V8Path <путь>` | нет | Каталог bin платформы (для wsap24.dll) |
| `-InfoBasePath <путь>` | * | Файловая база |
| `-InfoBaseServer <сервер>` | * | Сервер 1С (для серверной базы) |
| `-InfoBaseRef <имя>` | * | Имя базы на сервере |
| `-UserName <имя>` | нет | Имя пользователя |
| `-Password <пароль>` | нет | Пароль |
| `-AppName <имя>` | нет | Имя публикации (по умолчанию из имени каталога базы) |
| `-ApachePath <путь>` | нет | Корень Apache (по умолчанию `tools/apache24`) |
| `-Port <порт>` | нет | Порт (по умолчанию `8081`) |
| `-Manual` | нет | Не скачивать — только проверить и дать инструкцию |

> `*` — нужен либо `-InfoBasePath`, либо пара `-InfoBaseServer` + `-InfoBaseRef`

## Несколько пользователей одной базы

Повторный вызов с тем же AppName **заменяет** публикацию (идемпотентность). Это используется для:
- смены пользователя: «опубликуй под Ивановым» → тот же AppName, новый `-UserName`
- перезапуска после `/web-stop`: тот же вызов поднимает Apache обратно

Если пользователь просит **параллельную** публикацию под другим пользователем (для тестирования разных наборов прав), добавь суффикс к AppName:
- база `bpdemo`, пользователь `Иванов` → `-AppName bpdemo-ivanov`
- база `bpdemo`, пользователь `Admin` → `-AppName bpdemo-admin` (или просто `bpdemo`)

Ключевые слова: «ещё одну публикацию», «дополнительно», «параллельно», «под другим пользователем не убирая текущую».

## После выполнения

1. Сообщи URL-ы:
   - Веб-клиент: `http://localhost:{Port}/{AppName}`
   - OData: `http://localhost:{Port}/{AppName}/odata/standard.odata`
   - HTTP-сервисы: `http://localhost:{Port}/{AppName}/hs/<RootUrl>/...`
   - Web-сервисы: `http://localhost:{Port}/{AppName}/ws/<Имя>?wsdl`
2. Предложи открыть в браузере
3. Если нужно протестировать сервис — помоги составить запрос
4. Если база не зарегистрирована — предложи `/db-list add`

## Примеры

```powershell
# Файловая база
powershell.exe -NoProfile -File <skills-root>/web-publish/scripts/web-publish.ps1 -InfoBasePath "C:\Bases\MyDB" -UserName "Admin"

# С явным именем публикации и портом
powershell.exe -NoProfile -File <skills-root>/web-publish/scripts/web-publish.ps1 -InfoBasePath "C:\Bases\MyDB" -AppName "mydb" -Port 9090

# Серверная база
powershell.exe -NoProfile -File <skills-root>/web-publish/scripts/web-publish.ps1 -InfoBaseServer "srv01" -InfoBaseRef "MyDB" -UserName "Admin" -Password "secret"

# Ручной режим (только инструкция)
powershell.exe -NoProfile -File <skills-root>/web-publish/scripts/web-publish.ps1 -InfoBasePath "C:\Bases\MyDB" -Manual
```
