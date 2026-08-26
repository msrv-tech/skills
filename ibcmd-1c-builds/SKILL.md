---
name: ibcmd-1c-builds
description: Work with 1C:Enterprise configuration and extension build/update workflows through ibcmd. Use when Codex needs to import XML sources, build/save CF/CFE artifacts, load extensions into file infobases, run check/apply, diagnose ibcmd standalone runtime, authentication, .cfl locks, generation IDs, or compare Designer vs ibcmd paths for 1C updates and builds.
---

# ibcmd 1C Builds

## Core Rules

Prefer `ibcmd` for headless 1C configuration work when the user asks for builds, updates, loading CFE/CF, XML import/export, `check`, `apply`, or generation diagnostics.

For file infobases, always use a dedicated `--data` directory per operation or per workflow:

```powershell
--data "D:\path\project\.runtime\ibcmd-<operation>"
```

This avoids conflicts with the default standalone runtime at `%LOCALAPPDATA%\1C\1cv8\standalone-server`.

Do not run multiple `ibcmd` operations against the same file infobase in parallel. File bases need exclusive locks for most config operations.

If the infobase user has no password, pass only `--user "ИмяПользователя"` and omit `--password`. Empty `--password ""` can be treated as not supplied and may fail authentication.

## Preflight

Before mutating a base:

1. Identify platform versions:

```powershell
& "C:\Program Files\1cv8\8.5.1.1150\bin\ibcmd.exe" --version
```

2. Stop only leftover local client/tool processes from previous attempts when safe:

```powershell
Get-Process 1cv8,1cv8c,ibcmd -ErrorAction SilentlyContinue
```

3. If the user confirms nobody is in the file base, remove stale `.cfl` lock files:

```powershell
Get-ChildItem -LiteralPath "D:\bd\BaseName" -Force -Filter "*.cfl" | Remove-Item -Force
```

4. Probe access with `generation-id` before load/import:

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

## Designer Fallback

If `ibcmd` cannot authenticate or import but the user wants progress, use Designer `/F` as fallback. For passwordless users, pass `/N "Name"` and omit `/P`.

Prefer `ibcmd` again for final `check`, `apply`, `save`, and verification when it works.
