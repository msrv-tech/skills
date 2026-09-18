---
name: ibcmd-1c-builds
description: Work with 1C:Enterprise configuration and extension build/update workflows through ibcmd. Use when Codex needs to import XML sources, build/save CF/CFE artifacts, load extensions into file infobases, run check/apply, diagnose ibcmd standalone runtime, authentication, .cfl locks, generation IDs, or compare Designer vs ibcmd paths for 1C updates and builds.
---

# ibcmd 1C Builds

## Core Rules

Prefer `ibcmd` for headless 1C configuration work when the user asks for builds, updates, loading CFE/CF, XML import/export, `check`, `apply`, or generation diagnostics.

For file infobases, always use a dedicated `--data` directory per operation or per workflow:

```text
--data "<project-root>/.runtime/ibcmd-<operation>"
```

This avoids conflicts between standalone runtime operations. On Windows its
default state is under `%LOCALAPPDATA%\1C\1cv8\standalone-server`; on Linux use
an explicit writable `--data` directory and do not depend on a profile default.

Do not run multiple `ibcmd` operations against the same file infobase in parallel. File bases need exclusive locks for most config operations.

If the infobase user has no password, pass only `--user "ИмяПользователя"` and omit `--password`. Empty `--password ""` can be treated as not supplied and may fail authentication.

## Preflight

Before mutating a base, select the backend explicitly. Windows uses
`<platform>/bin/ibcmd.exe`; Linux support requires 1С 8.5 `ibcmd` and uses
either `/opt/1cv8/x86_64/<version>/ibcmd` or
`/opt/1cv8/x86_64/<version>/bin/ibcmd`, depending on the package layout.
An exact executable path is always valid. When resolving a version directory,
accept exactly one of those candidates; if both exist, stop and require an
exact path. If `/opt/1cv8/env` exists and is readable, it may be sourced, but
8.5 packages are not required to create it.

1. Identify platform versions:

Linux:

```bash
if [ -r /opt/1cv8/env ]; then
  . /opt/1cv8/env
fi
export ONEC_IBCMD_PATH=/opt/1cv8/x86_64/<version>/ibcmd
"$ONEC_IBCMD_PATH" --version
```

Windows:

```powershell
& "C:\Program Files\1cv8\8.5.1.1150\bin\ibcmd.exe" --version
```

2. Check for leftover local client/tool processes from previous attempts. Do
not terminate them without explicit user approval:

```powershell
Get-Process 1cv8,1cv8c,ibcmd -ErrorAction SilentlyContinue
```

Linux:

```bash
pgrep -a -f '(^|/)(1cv8|1cv8c|ibcmd)( |$)' || true
```

3. If a lock remains, report it. Remove stale `.cfl` files only after the user
confirms that nobody is using the file base.

4. Probe access with `generation-id` before load/import. Linux:

```bash
"$ONEC_IBCMD_PATH" config \
  --data "<project-root>/.runtime/ibcmd-probe" \
  --database-path "<test-infobase-path>" \
  --user "<test-user>" \
  generation-id
```

Windows:

```powershell
$data = "D:\repo\.runtime\ibcmd-probe"
New-Item -ItemType Directory -Force -Path $data | Out-Null
& "<platform>\bin\ibcmd.exe" config `
  --data $data `
  --database-path "D:\bd\BaseName" `
  --user "Александр" `
  generation-id
```

If an older platform says the configuration requires a newer platform, switch to the newer installed platform.

## Loading a CFE Into a File Base

Use this sequence:

```powershell
$ibcmd = "C:\Program Files\1cv8\8.5.1.1150\bin\ibcmd.exe"
$db = "D:\bd\BaseName"
$cfe = "D:\repo\extensions\my-extension\MyExtension.cfe"
$ext = "ИмяРасширения"
$user = "Александр"

& $ibcmd config --data "D:\repo\.runtime\ibcmd-load" --database-path $db --user $user `
  load --extension $ext --force $cfe

& $ibcmd config --data "D:\repo\.runtime\ibcmd-check" --database-path $db --user $user `
  check --extension $ext --force

& $ibcmd config --data "D:\repo\.runtime\ibcmd-apply" --database-path $db --user $user `
  apply --extension $ext --force --dynamic=disable --session-terminate=force
```

Run operations sequentially. Do not run `extension list` in parallel with `check/apply`.

## Importing XML Sources Into an Extension

Use this when source XML in `xml/` must become the loaded extension:

```powershell
& $ibcmd config --data "D:\repo\.runtime\ibcmd-import" --database-path $db --user $user `
  import --extension $ext "D:\repo\xml"

& $ibcmd config --data "D:\repo\.runtime\ibcmd-check" --database-path $db --user $user `
  check --extension $ext --force

& $ibcmd config --data "D:\repo\.runtime\ibcmd-apply" --database-path $db --user $user `
  apply --extension $ext --force --dynamic=disable --session-terminate=force
```

If import fails with `Отсутствует внутренняя информация (узел InternalInfo)`, add valid `xr:GeneratedType` entries to the XML object or seed them from a full export. Adopted documents usually need generated types for Object, Ref, Selection, List, and Manager.

## Saving the Built Artifact

After a successful import/load and apply, save the current extension to CFE:

```powershell
& $ibcmd config --data "D:\repo\.runtime\ibcmd-save-cfe" --database-path $db --user $user `
  save --extension $ext "D:\repo\extensions\my-extension\MyExtension.cfe"
```

Verify:

```powershell
& $ibcmd config --data "D:\repo\.runtime\ibcmd-list" --database-path $db --user $user `
  extension list

Get-FileHash -Algorithm SHA256 "D:\repo\extensions\my-extension\MyExtension.cfe"
```

## Exporting XML

Export an extension from a base:

```powershell
& $ibcmd config --data "D:\repo\.runtime\ibcmd-export" --database-path $db --user $user `
  export --extension $ext --force "D:\repo\.runtime\export-extension"
```

Export can be used as a seed for missing XML internals.

## Diagnostics

`Ошибка исключительной блокировки информационной базы`:
Check for live `1cv8/1cv8c/ibcmd` processes, then stale `.cfl` files if the user confirms nobody is in the file base.

`Для выполнения операции требуется аутентификация`:
Use the actual infobase user. If passwordless, pass `--user "Name"` only.

`ibcmd` hangs on a file base:
Clean only the workflow runtime directories and the default standalone runtime if no `ibcmd` is running. Then retry `generation-id` with a fresh `--data`.

```powershell
Get-Process ibcmd -ErrorAction SilentlyContinue
Remove-Item "D:\repo\.runtime\ibcmd-*" -Recurse -Force
Remove-Item "$env:LOCALAPPDATA\1C\1cv8\standalone-server\*" -Recurse -Force
```

`ibcmd --database-path` for a file base starts/uses a 1C standalone runtime. This is separate from a normal 1C server cluster. The base remains a file base; `--data` is only the standalone runtime work directory.

## Backend Boundaries

`ibcmd` and Designer are separate backends. Do not switch between them
automatically. If `ibcmd` cannot authenticate, import, check, apply, or save,
stop and report the exact error. Use Designer only when the user explicitly
requests the Designer backend.

Win32 desktop isolation and UIA are Windows-only and are not part of this
skill. Linux headless UI uses the `codex-test-bridge` Xvfb
TestClient/TestManager backend.
