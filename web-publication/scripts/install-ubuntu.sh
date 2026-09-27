#!/bin/sh
set -eu

usage() {
    echo "Usage: sudo $0 (--ws-deb /path/to/official-ws.deb | --installer-run /path/to/setup-full.run) --platform-version 8.x.x.x" >&2
}

WS_DEB=
INSTALLER_RUN=
PLATFORM_VERSION=
while [ "$#" -gt 0 ]; do
    case "$1" in
        --ws-deb)
            [ "$#" -ge 2 ] || { usage; exit 2; }
            WS_DEB=$2
            shift 2
            ;;
        --installer-run)
            [ "$#" -ge 2 ] || { usage; exit 2; }
            INSTALLER_RUN=$2
            shift 2
            ;;
        --platform-version)
            [ "$#" -ge 2 ] || { usage; exit 2; }
            PLATFORM_VERSION=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

[ -n "$WS_DEB" ] || [ -n "$INSTALLER_RUN" ] ||
    { echo "Error: --ws-deb or --installer-run is required; no package will be downloaded" >&2; exit 2; }
[ -z "$WS_DEB" ] || [ -z "$INSTALLER_RUN" ] ||
    { echo "Error: specify only one of --ws-deb and --installer-run" >&2; exit 2; }
[ -n "$PLATFORM_VERSION" ] || { echo "Error: --platform-version is required" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "Error: run this installer as root (for example, with sudo)" >&2; exit 1; }

case "$PLATFORM_VERSION" in
    *[!0-9.]*|"") echo "Error: invalid platform version: $PLATFORM_VERSION" >&2; exit 2 ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y apache2

if [ -n "$WS_DEB" ]; then
    [ -f "$WS_DEB" ] || { echo "Error: WS DEB not found: $WS_DEB" >&2; exit 1; }
    command -v dpkg-deb >/dev/null 2>&1 || { echo "Error: dpkg-deb is required" >&2; exit 1; }
    PACKAGE=$(dpkg-deb -f "$WS_DEB" Package)
    VERSION=$(dpkg-deb -f "$WS_DEB" Version)
    ARCH=$(dpkg-deb -f "$WS_DEB" Architecture)

    case "$PACKAGE" in
        1c-enterprise-*-ws|1c-enterprise-ws) ;;
        *) echo "Error: DEB package is not an official 1C WS package by metadata: $PACKAGE" >&2; exit 1 ;;
    esac
    case "$PACKAGE $VERSION" in
        *"$PLATFORM_VERSION"*) ;;
        *) echo "Error: WS package version does not match requested platform $PLATFORM_VERSION ($PACKAGE $VERSION)" >&2; exit 1 ;;
    esac
    case "$ARCH" in
        amd64|x86_64) ;;
        *) echo "Error: unsupported WS package architecture: $ARCH" >&2; exit 1 ;;
    esac
    apt-get install -y "$WS_DEB"
else
    [ -f "$INSTALLER_RUN" ] || { echo "Error: official installer not found: $INSTALLER_RUN" >&2; exit 1; }
    [ -x "$INSTALLER_RUN" ] || { echo "Error: official installer is not executable: $INSTALLER_RUN" >&2; exit 1; }
    INSTALLER_VERSION=$("$INSTALLER_RUN" --version)
    case "$INSTALLER_VERSION" in
        *"$PLATFORM_VERSION"*) ;;
        *) echo "Error: installer version does not match requested platform $PLATFORM_VERSION ($INSTALLER_VERSION)" >&2; exit 1 ;;
    esac
    "$INSTALLER_RUN" --mode unattended --enable-components ws --installer-language ru
fi

command -v apache2ctl >/dev/null 2>&1 || { echo "Error: apache2ctl was not installed" >&2; exit 1; }
WEBINST=$(find "/opt/1cv8/x86_64/$PLATFORM_VERSION" -maxdepth 2 -type f -name webinst -perm -0100 -print -quit)
WSAP=$(find "/opt/1cv8/x86_64/$PLATFORM_VERSION" -maxdepth 2 -type f -name wsap24.so -print -quit)
[ -n "$WEBINST" ] || { echo "Error: matching webinst not found after WS package installation" >&2; exit 1; }
[ -n "$WSAP" ] || { echo "Error: matching wsap24.so not found after WS package installation" >&2; exit 1; }
if ldd "$WSAP" | grep -q "not found"; then
    echo "Error: wsap24.so has unresolved shared-library dependencies" >&2
    ldd "$WSAP" >&2
    exit 1
fi
mkdir -p /etc/systemd/system/apache2.service.d
printf '[Service]\nMemoryDenyWriteExecute=no\n' > /etc/systemd/system/apache2.service.d/1c-web.conf
systemctl daemon-reload
systemctl restart apache2
[ "$(systemctl show apache2 -p MemoryDenyWriteExecute --value)" = "no" ] ||
    { echo "Error: Apache MemoryDenyWriteExecute remains enabled" >&2; exit 1; }
apache2ctl configtest

echo "Apache and matching 1C web components installed successfully"
echo "webinst: $WEBINST"
echo "wsap24.so: $WSAP"
