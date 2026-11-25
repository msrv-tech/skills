#!/usr/bin/env python3
"""Install/update Bridge in registered demo databases; sync local Codex skills."""
import argparse
import importlib.util
import os
import json
import tempfile
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common.test_database_registry import resolve_registry

spec = importlib.util.spec_from_file_location(
    'bridge_update', ROOT / 'codex-test-bridge/scripts/update_all_test_databases.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def detect_compatibility(record, platform, timeout):
    spec = importlib.util.spec_from_file_location(
        'bridge_installer', ROOT / 'codex-test-bridge/scripts/install_cfe_designer_hidden.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    with tempfile.TemporaryDirectory(prefix='ctb-compatibility-') as work:
        work = Path(work)
        output = work / 'xml'
        output.mkdir()
        objects = work / 'objects.txt'
        objects.write_text('Configuration', encoding='utf-8-sig')
        log = work / 'designer.log'
        command = [str(platform), 'DESIGNER',
                   f"/S{record['Srvr']}\\{record['Ref']}",
                   f"/N{record['User']}",
                   '/P""' if not record.get('Password') else f"/P{record['Password']}",
                   '/DisableStartupDialogs', '/DisableStartupMessages',
                   '/DumpConfigToFiles', str(output), '-Format', 'Hierarchical',
                   '-listFile', str(objects), '/Out', str(log)]
        backend, display = installer.create_installer_backend()
        process = None
        try:
            process = backend.start(command)
            if os.name != 'nt':
                installer.submit_linux_authentication(display, record['User'], record.get('Password', ''), process)
            code = installer.wait_for_process(process, timeout)
            if code != 0 or not (output / 'Configuration.xml').is_file():
                raise bridge.UpdateError('Compatibility metadata export failed')
            return bridge.read_compatibility_mode({'path': str(output)})
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                process.close()
            backend.close()


def enable_publication(record):
    publication = record.get('WebPublication')
    if not publication:
        return
    host = publication['SshHost']
    container = str(int(publication['Container']))
    path = publication['VrdPath']
    module = (ROOT / 'codex-test-bridge/scripts/enable_vrd_linux.py').read_text()
    # Execute the bundled VRD updater, keeping target paths in the private registry.
    program = ("import shutil, time\nfrom pathlib import Path\nnamespace={'__name__':'bridge_vrd'}\n"
               + 'exec(' + repr(module) + ',namespace)\n'
               + 'path=Path(' + repr(path) + ')\n'
               + "backup=path.with_name(path.name+'.ctb-backup-'+str(time.time_ns()))\n"
               + "shutil.copy2(path,backup)\n"
               + "namespace['update_vrd'](path,'CodexTestBridge','codex-test')\n"
               + "import subprocess\nsubprocess.run(['apache2ctl','configtest'],check=True)\n"
               + "subprocess.run(['systemctl','reload','apache2'],check=True)\n")
    completed = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                                host, 'pct', 'exec', container, '--', 'python3', '-'],
                               input=program, text=True, capture_output=True, timeout=60)
    if completed.returncode:
        raise bridge.UpdateError('HTTP publication update failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', help='Private registry override')
    parser.add_argument('--platform', default=os.environ.get('CODEX_1C_EXECUTABLE', ''))
    parser.add_argument('--refresh-compatibility', action='store_true', help='Read compatibility via Designer and save to private registry')
    parser.add_argument('--database', action='append', help='Registered Ref; repeatable')
    parser.add_argument('--dry-run', action='store_true', help='Validate without changes')
    parser.add_argument('--verify-only', action='store_true', help='Check installed Bridge without installing or syncing')
    parser.add_argument('--sync-only', action='store_true', help='Only install local Codex skills')
    parser.add_argument('--timeout', type=float, default=900)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    destinations = {'Codex': bridge.default_codex_skills_dir()}
    if args.sync_only:
        bridge.sync_local_skills(ROOT, destinations, dry_run=args.dry_run)
        print('Codex skills: ready' if args.dry_run else 'Codex skills: updated')
        return 0
    registry_path = resolve_registry(args.registry)
    records = bridge.load_registry(registry_path)
    platform = Path(args.platform)
    if not args.platform:
        versions = {b.get('Designer', {}).get('PlatformVersion') for b in records}
        candidates = [Path('/opt/1cv8/x86_64') / v / '1cv8' for v in versions if v]
        available = [p for p in candidates if p.is_file()]
        if len(available) == 1:
            args.platform = str(available[0])
            platform = available[0]
    requested = args.database or ['unf1', 'bp1']
    selected = []
    # Validate every target before changing any infobase or local skills.
    for name in requested:
        matches = [b for b in records if b.get('Ref', '').casefold() == name.casefold()]
        if len(matches) != 1:
            raise bridge.UpdateError('Target must match exactly one registered database')
        record = matches[0]
        reason = bridge.unsupported_database_reason(record)
        if reason:
            raise bridge.UpdateError('Target lacks Srvr/Ref or Bridge.BaseUrl; configure the private registry')
        bridge.validate_registered_credentials(record)
        if args.refresh_compatibility:
            if not args.platform or not platform.is_file():
                raise bridge.UpdateError('Compatibility detection requires --platform')
            record['BridgeCompatibilityMode'] = detect_compatibility(record, platform.resolve(), args.timeout)
        variant = bridge.cfe_variant(bridge.read_compatibility_mode(record))
        cfe = ROOT / 'codex-test-bridge' / ('codex-test-bridge.cfe' if variant == 'full' else 'codex-test-bridge-legacy.cfe')
        if not cfe.is_file() or not cfe.stat().st_size:
            raise bridge.UpdateError('Required CFE is missing or empty')
        selected.append((record, cfe))
    if args.refresh_compatibility:
        data = json.loads(registry_path.read_text(encoding='utf-8-sig'))
        modes = {r['Ref']: r['BridgeCompatibilityMode'] for r, _ in selected}
        for entry in data['databases']:
            if entry.get('Ref') in modes:
                entry['BridgeCompatibilityMode'] = modes[entry['Ref']]
        registry_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    if not args.dry_run and not args.verify_only and (not args.platform or not platform.is_file()):
        raise bridge.UpdateError('Set --platform or CODEX_1C_EXECUTABLE to the server-compatible 1cv8 executable')
    if not args.verify_only:
        bridge.sync_local_skills(ROOT, destinations, dry_run=args.dry_run)
    for index, (record, cfe) in enumerate(selected, 1):
        if args.dry_run:
            print(f'Target {index}: ready')
            continue
        # Do not require an existing HTTP bridge before first installation.
        if not args.verify_only:
            print(f'Target {index}: installing CFE', flush=True)
            bridge.install_database(record, platform.resolve(), cfe, args.timeout)
            print(f'Target {index}: enabling publication and checking HTTP', flush=True)
            enable_publication(record)
        bridge.verify_bridge(record, bridge.source_bridge_version())
        bridge.assert_no_bootstrap_users(record)
        print(f'Target {index}: verified' if args.verify_only else f'Target {index}: installed and verified', flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Child diagnostics may contain connection values; keep output private-safe.
        print(f'Deployment stopped ({type(exc).__name__}). Check registry, compatibility mode, platform and HTTP publication.', file=sys.stderr)
        raise SystemExit(1)
