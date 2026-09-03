#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenario_runner import (
    ScenarioRunner,
    collect_scenario_files,
    load_scenario,
    run_suite,
    save_junit_report,
    save_report,
)
from ui_worker import load_worker_config, run_ui_worker
from agent_ui import normalize_ui_report
from hybrid_runner import run_hybrid_scenario
from ui_batch import run_ui_batch
from bridge_doctor import run_doctor


REQUEST_TIMEOUT = 60.0

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def compact_ui_result(result: dict, report_path: str = "") -> dict:
    manager_result = result.get("managerResult") if isinstance(result.get("managerResult"), dict) else {}
    steps = manager_result.get("steps") if isinstance(manager_result.get("steps"), list) else []
    return {
        "ok": result.get("ok", False),
        "runId": result.get("runId"),
        "status": result.get("status"),
        "durationMs": result.get("durationMs"),
        "steps": len(steps),
        "failedSteps": len([step for step in steps if isinstance(step, dict) and step.get("status") == "failed"]),
        "error": result.get("error"),
        "report": str(Path(report_path).resolve()) if report_path else None,
        "artifacts": result.get("artifacts", {}),
    }


def decode_json_object(data: str) -> dict:
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError("Bridge response must be a JSON object")
    return result


def request_json(url: str, payload: dict | None = None) -> dict:
    if payload is None:
        req = urllib.request.Request(url, method="GET")
    else:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=REQUEST_TIMEOUT) as response:
            data = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        data = exc.read().decode("utf-8", errors="replace")
        try:
            result = decode_json_object(data)
        except (json.JSONDecodeError, ValueError):
            result = {"ok": False, "error": data or str(exc)}
        result["httpStatus"] = exc.code
        return result
    result = decode_json_object(data)
    if status >= 400:
        result.setdefault("ok", False)
        result["httpStatus"] = status
    return result


def main() -> int:
    global REQUEST_TIMEOUT
    parser = argparse.ArgumentParser(description="Call CodexTestBridge HTTP service")
    parser.add_argument("--base-url", default="", help="Bridge base URL; not required for run-ui")
    parser.add_argument("--timeout", type=float, default=60, help="HTTP timeout in seconds (default: 60)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health")
    sub.add_parser("capabilities", help="Show machine-readable bridge and UI capabilities")
    doctor = sub.add_parser("doctor", help="Check bridge contract and optionally validate a UI worker config")
    doctor.add_argument("--worker-config", default="", help="Validate this UI worker configuration without launching 1C")

    metadata = sub.add_parser("metadata")
    metadata.add_argument("--sections", default="", help="Comma-separated: catalogs,documents,enums,informationRegisters,accumulationRegisters")

    describe = sub.add_parser("describe")
    describe.add_argument("kind", help="catalog, document, enum")
    describe.add_argument("name")

    query = sub.add_parser("query")
    query.add_argument("text")
    query.add_argument("--limit", type=int, default=100)
    query.add_argument("--params", default="{}", help="JSON object")

    execute_bsl = sub.add_parser("execute-bsl")
    execute_bsl.add_argument("code", help="1C code for Выполнить(). Set РезультатВыполнения to return a value")
    execute_bsl.add_argument("--params", default="[]", help="JSON array available as Параметры")

    call_common = sub.add_parser("call-common-module")
    call_common.add_argument("module", help="Common module name")
    call_common.add_argument("method", help="Export method name")
    call_common.add_argument("--params", default="[]", help="JSON array of method arguments")
    call_common.add_argument("--no-result", action="store_true", help="Call procedure without assigning result")

    get_object = sub.add_parser("get-object")
    get_object.add_argument("kind", help="catalog, document, enum")
    get_object.add_argument("name")
    get_object.add_argument("uuid")
    get_object.add_argument("--no-tables", action="store_true")

    write_object = sub.add_parser("write-object")
    write_object.add_argument("kind", help="catalog or document")
    write_object.add_argument("name")
    write_object.add_argument("--uuid", default="")
    write_object.add_argument("--fields", default="{}", help="JSON object")
    write_object.add_argument("--tables", default="{}", help="JSON object")
    write_object.add_argument("--write-mode", choices=["write", "post"], default="write")
    write_object.add_argument("--append-tables", action="store_true")

    delete_object = sub.add_parser("delete-object")
    delete_object.add_argument("kind", help="catalog or document")
    delete_object.add_argument("name")
    delete_object.add_argument("uuid")
    delete_object.add_argument("--clear", action="store_true", help="Clear deletion mark instead of setting it")

    catalog = sub.add_parser("create-catalog-item")
    catalog.add_argument("catalog")
    catalog.add_argument("--fields", required=True, help="JSON object")

    doc = sub.add_parser("create-document")
    doc.add_argument("document")
    doc.add_argument("--fields", default="{}", help="JSON object")
    doc.add_argument("--tables", default="{}", help="JSON object")
    doc.add_argument("--post", action="store_true")

    render = sub.add_parser("render-print-form")
    render.add_argument("external_path", help="Path visible to the 1C server")
    render.add_argument("--output-dir", required=True, help="Directory visible to the 1C server")
    render.add_argument("--output-name", default="print-result")
    render.add_argument("--assignment", default="", help="Example: Документ.ЗаказПокупателя")
    render.add_argument("--document-name", default="", help="Example: ЗаказПокупателя")
    render.add_argument("--uuid", default="", help="Specific document ref UUID")

    render_report = sub.add_parser("render-report")
    render_report.add_argument("external_path", help="Path visible to the 1C server")
    render_report.add_argument("--output-dir", required=True, help="Directory visible to the 1C server")
    render_report.add_argument("--output-name", default="report-result")
    render_report.add_argument("--params", default="{}", help="JSON object passed to СформироватьОтчетДляТеста")

    scenario = sub.add_parser("run-scenario", help="Run a declarative headless JSON scenario")
    scenario.add_argument("scenario_file", help="Path to scenario JSON")
    scenario.add_argument("--report", default="", help="Write the complete JSON report to this path")

    suite = sub.add_parser("run-suite", help="Run a scenario file or all *.scenario.json files in a directory")
    suite.add_argument("scenario_path", help="Scenario file or directory searched recursively for *.scenario.json")
    suite.add_argument("--report", default="", help="Write aggregate JSON report to this path")
    suite.add_argument("--junit", default="", help="Write JUnit XML report to this path")
    suite.add_argument("--fail-fast", action="store_true", help="Stop after the first failed scenario")

    ui = sub.add_parser("run-ui", help="Run native 1C TestClient/TestManager in an isolated desktop")
    ui.add_argument("worker_config", help="Path to UI worker JSON configuration")
    ui.add_argument("scenario_file", help="Path passed to the 1C test manager as {scenario}")
    ui.add_argument("--artifact-dir", default="artifacts/ui", help="Directory for manager and worker artifacts")
    ui.add_argument("--report", default="", help="Write worker JSON report to this path")
    ui.add_argument("--full-output", action="store_true", help="Print the complete UI tree instead of a compact summary")

    ui_batch = sub.add_parser("run-ui-batch", help="Run UI scenarios in one warm client/manager lifecycle")
    ui_batch.add_argument("worker_config")
    ui_batch.add_argument("scenario_files", nargs="+")
    ui_batch.add_argument("--artifact-dir", default="artifacts/ui-batch")
    ui_batch.add_argument("--report", default="")
    ui_batch.add_argument("--full-output", action="store_true")

    inspect = sub.add_parser("ui-inspect", help="Open an optional link and return an agent-normalized UI map")
    inspect.add_argument("worker_config")
    inspect.add_argument("--link", default="")
    inspect.add_argument("--uuid", default="")
    inspect.add_argument("--kind", choices=["catalog", "document"], default="catalog")
    inspect.add_argument("--metadata-name", default="")
    inspect.add_argument("--depth", type=int, default=8)
    inspect.add_argument("--artifact-dir", default="artifacts/ui-inspect")
    inspect.add_argument("--report", default="")

    hybrid = sub.add_parser("run-hybrid", help="Run server arrange, native UI act, server assert, cleanup")
    hybrid.add_argument("worker_config")
    hybrid.add_argument("scenario_file")
    hybrid.add_argument("--artifact-dir", default="artifacts/hybrid")
    hybrid.add_argument("--report", default="")

    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    REQUEST_TIMEOUT = args.timeout
    local_commands = {"run-ui", "run-ui-batch", "ui-inspect"}
    if args.cmd not in local_commands and not args.base_url:
        parser.error("--base-url is required for this command")
    base_url = args.base_url.rstrip("/")

    if args.cmd == "health":
        result = request_json(f"{base_url}/health")
    elif args.cmd == "capabilities":
        result = request_json(f"{base_url}/command", {"command": "Capabilities"})
    elif args.cmd == "doctor":
        result = run_doctor(
            lambda: request_json(f"{base_url}/health"),
            lambda: request_json(f"{base_url}/command", {"command": "Capabilities"}),
            args.worker_config,
        )
    elif args.cmd == "metadata":
        payload = {"command": "Metadata"}
        if args.sections:
            payload["sections"] = [item.strip() for item in args.sections.split(",") if item.strip()]
        result = request_json(f"{base_url}/command", payload)
    elif args.cmd == "describe":
        result = request_json(f"{base_url}/command", {"command": "Describe", "kind": args.kind, "name": args.name})
    elif args.cmd == "query":
        result = request_json(
            f"{base_url}/command",
            {"command": "Query", "text": args.text, "limit": args.limit, "params": json.loads(args.params)},
        )
    elif args.cmd == "execute-bsl":
        result = request_json(
            f"{base_url}/command",
            {"command": "ExecuteBSL", "code": args.code, "params": json.loads(args.params)},
        )
    elif args.cmd == "call-common-module":
        result = request_json(
            f"{base_url}/command",
            {
                "command": "CallCommonModule",
                "module": args.module,
                "method": args.method,
                "params": json.loads(args.params),
                "expectResult": not args.no_result,
            },
        )
    elif args.cmd == "get-object":
        result = request_json(
            f"{base_url}/command",
            {
                "command": "GetObject",
                "kind": args.kind,
                "name": args.name,
                "uuid": args.uuid,
                "includeTables": not args.no_tables,
            },
        )
    elif args.cmd == "write-object":
        result = request_json(
            f"{base_url}/command",
            {
                "command": "WriteObject",
                "kind": args.kind,
                "name": args.name,
                "uuid": args.uuid,
                "fields": json.loads(args.fields),
                "tables": json.loads(args.tables),
                "writeMode": args.write_mode,
                "clearTables": not args.append_tables,
            },
        )
    elif args.cmd == "delete-object":
        result = request_json(
            f"{base_url}/command",
            {
                "command": "DeleteObject",
                "kind": args.kind,
                "name": args.name,
                "uuid": args.uuid,
                "deletionMark": not args.clear,
            },
        )
    elif args.cmd == "create-catalog-item":
        result = request_json(
            f"{base_url}/command",
            {"command": "CreateCatalogItem", "catalog": args.catalog, "fields": json.loads(args.fields)},
        )
    elif args.cmd == "create-document":
        result = request_json(
            f"{base_url}/command",
            {
                "command": "CreateDocument",
                "document": args.document,
                "fields": json.loads(args.fields),
                "tables": json.loads(args.tables),
                "writeMode": "post" if args.post else "write",
            },
        )
    elif args.cmd == "render-print-form":
        result = request_json(
            f"{base_url}/command",
            {
                "command": "RenderExternalPrintForm",
                "externalPath": args.external_path,
                "outputDir": args.output_dir,
                "outputName": args.output_name,
                "assignment": args.assignment,
                "documentName": args.document_name,
                "uuid": args.uuid,
            },
        )
    elif args.cmd == "render-report":
        result = request_json(
            f"{base_url}/command",
            {
                "command": "RenderExternalReport",
                "externalPath": args.external_path,
                "outputDir": args.output_dir,
                "outputName": args.output_name,
                "reportParams": json.loads(args.params),
            },
        )
    elif args.cmd == "run-scenario":
        definition = load_scenario(args.scenario_file)
        runner = ScenarioRunner(lambda payload: request_json(f"{base_url}/command", payload))
        result = runner.run(definition)
        if args.report:
            save_report(result, args.report)
    elif args.cmd == "run-suite":
        runner = ScenarioRunner(lambda payload: request_json(f"{base_url}/command", payload))
        result = run_suite(runner, collect_scenario_files(args.scenario_path), fail_fast=args.fail_fast)
        if args.report:
            save_report(result, args.report)
        if args.junit:
            save_junit_report(result, args.junit)
    elif args.cmd == "run-ui":
        if args.report:
            report_path = Path(args.report)
            if report_path.is_file():
                report_path.unlink()
        result = run_ui_worker(load_worker_config(args.worker_config), args.scenario_file, args.artifact_dir)
        if args.report:
            save_report(result, args.report)
        output_result = result if args.full_output else compact_ui_result(result, args.report)
    elif args.cmd == "run-ui-batch":
        result = run_ui_batch(load_worker_config(args.worker_config), args.scenario_files, args.artifact_dir)
        if args.report:
            save_report(result, args.report)
        output_result = result if args.full_output else compact_ui_result(result, args.report)
    elif args.cmd == "ui-inspect":
        if args.uuid and not args.metadata_name:
            parser.error("ui-inspect --uuid requires --metadata-name")
        inspect_steps = []
        if args.link or args.uuid:
            step = {"action": "openNavigationLink"}
            if args.link:
                step["link"] = args.link
            else:
                step.update({"uuid": args.uuid, "kind": args.kind, "metadataName": args.metadata_name})
            inspect_steps.append(step)
        inspect_steps.append({"action": "inspectUi", "depth": args.depth})
        artifact_dir = Path(args.artifact_dir).resolve()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        scenario_path = artifact_dir / "inspect.ui.json"
        scenario_path.write_text(json.dumps({"name": "agent UI inspect", "steps": inspect_steps}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = run_ui_worker(load_worker_config(args.worker_config), scenario_path, artifact_dir)
        if args.report:
            save_report(result, args.report)
        output_result = normalize_ui_report(result)
    elif args.cmd == "run-hybrid":
        definition_path = Path(args.scenario_file).resolve()
        definition = json.loads(definition_path.read_text(encoding="utf-8-sig"))
        result = run_hybrid_scenario(
            definition, definition_path,
            lambda payload: request_json(f"{base_url}/command", payload),
            load_worker_config(args.worker_config), args.artifact_dir,
        )
        if args.report:
            save_report(result, args.report)
        output_result = result
    else:
        raise AssertionError(args.cmd)

    print(json.dumps(output_result if args.cmd in {"run-ui", "run-ui-batch", "ui-inspect", "run-hybrid"} else result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
