"""Install a workspace-local Android build toolchain; no global PATH changes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / '.local' / 'android'


def download(url, path, checksum=None, algorithm='sha256'):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        print('Downloading', path.name, flush=True)
        request = urllib.request.Request(url, headers={'User-Agent': 'GrowthBuild/1.0'})
        with urllib.request.urlopen(request, timeout=120) as response, path.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    if checksum and hashlib.new(algorithm, path.read_bytes()).hexdigest() != checksum:
        raise RuntimeError(f'Checksum mismatch: {path}')
    return path


def install():
    TOOLS.mkdir(parents=True, exist_ok=True)
    jdks = list(TOOLS.glob('jdk-*/bin/java.exe'))
    if not jdks:
        url = 'https://aka.ms/download-jdk/microsoft-jdk-17.0.20.1-windows-x64.zip'
        with urllib.request.urlopen(url + '.sha256sum.txt', timeout=60) as response:
            checksum = response.read().decode().split()[0]
        archive = download(url, TOOLS / 'downloads/microsoft-jdk-17.zip', checksum)
        with zipfile.ZipFile(archive) as z:
            z.extractall(TOOLS)
        jdks = list(TOOLS.glob('jdk-*/bin/java.exe'))
    jdk = jdks[0].parents[1]
    gradle = TOOLS / 'gradle-8.13'
    if not gradle.exists():
        url = 'https://downloads.gradle.org/distributions/gradle-8.13-bin.zip'
        with urllib.request.urlopen(url + '.sha256', timeout=60) as response:
            checksum = response.read().decode().strip()
        with zipfile.ZipFile(download(url, TOOLS / 'downloads/gradle-8.13-bin.zip', checksum)) as z:
            z.extractall(TOOLS)
    sdk = TOOLS / 'sdk'
    manager = sdk / 'cmdline-tools/19.0/bin/sdkmanager.bat'
    if not manager.exists():
        with urllib.request.urlopen('https://dl.google.com/android/repository/repository2-3.xml', timeout=90) as response:
            tree = ET.fromstring(response.read())
        packages = []
        for item in tree.findall('remotePackage'):
            if item.attrib.get('path', '') == 'cmdline-tools;19.0':
                for archive in item.findall('archives/archive'):
                    if archive.findtext('host-os') == 'windows':
                        packages.append((int(item.findtext('revision/major')), archive.find('complete')))
        _, archive = max(packages, key=lambda row: row[0])
        archive_path = download('https://dl.google.com/android/repository/' + archive.findtext('url'), TOOLS / 'downloads/cmdline-tools-19.zip', archive.findtext('checksum'), 'sha1')
        destination = sdk / 'cmdline-tools/19.0'
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path) as z:
            for item in z.infolist():
                relative = Path(item.filename).relative_to('cmdline-tools')
                target = destination / relative
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(item))
    env = dict(os.environ, JAVA_HOME=str(jdk), ANDROID_HOME=str(sdk), ANDROID_SDK_ROOT=str(sdk), GRADLE_USER_HOME=str(TOOLS / 'gradle-cache'))
    env['PATH'] = str(jdk / 'bin') + os.pathsep + env['PATH']
    if not (sdk / 'platforms/android-36/android.jar').exists() or not (sdk / 'build-tools/35.0.0/apksigner.bat').exists():
        print('Installing Android SDK packages', flush=True)
        subprocess.run([str(manager), f'--sdk_root={sdk}', '--licenses'], input='y\n' * 100, text=True, env=env, check=True)
        subprocess.run([str(manager), f'--sdk_root={sdk}', 'platforms;android-36', 'build-tools;35.0.0', 'platform-tools'], input='y\n' * 100, text=True, env=env, check=True)
    if not (sdk / 'platforms/android-36/android.jar').exists():
        raise RuntimeError('Android platform 36 installation did not complete')
    (TOOLS / 'environment.json').write_text(json.dumps({'java':str(jdk), 'sdk':str(sdk), 'gradle':str(gradle)}, indent=2))
    print('Android toolchain ready:', TOOLS, flush=True)
    return env


if __name__ == '__main__':
    install()
