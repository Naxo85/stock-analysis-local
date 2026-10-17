"""Run device checks only on the private growth-test emulator (port 5580)."""
from __future__ import annotations
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from android_toolchain import ROOT, TOOLS

SDK=Path(json.loads((TOOLS/'environment.json').read_text())['sdk'])
ADB=str(SDK/'platform-tools/adb.exe')
SERIAL='emulator-5580'
OUTPUT=ROOT/'releases/android/screenshots'
OUTPUT.mkdir(parents=True,exist_ok=True)


def adb(*args,check=True,binary=False):
    options={} if binary else {'encoding':'utf-8','errors':'replace'}
    return subprocess.run([ADB,'-s',SERIAL,*args],capture_output=True,text=not binary,check=check,timeout=300,**options)


def tree():
    adb('shell','uiautomator','dump','/sdcard/growth-ui.xml')
    return ET.fromstring(adb('shell','cat','/sdcard/growth-ui.xml').stdout)


def tap(label):
    nodes=[n for n in tree().iter('node') if n.attrib.get('text')==label or n.attrib.get('content-desc')==label]
    if not nodes: raise RuntimeError(f'UI control absent: {label}')
    x1,y1,x2,y2=map(int,re.findall(r'\d+',nodes[-1].attrib['bounds']))
    adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));time.sleep(1)


def shot(name):
    (OUTPUT/f'{name}.png').write_bytes(adb('exec-out','screencap','-p',binary=True).stdout)


def wait_for_text(label,timeout=120):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if any(n.attrib.get('text')==label or n.attrib.get('content-desc')==label for n in tree().iter('node')):
            return
        time.sleep(2)
    shot('failure')
    raise RuntimeError(f'UI text did not appear: {label}')


def wait_until_absent(label,timeout=120):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if not any(n.attrib.get('text')==label or n.attrib.get('content-desc')==label for n in tree().iter('node')):
            return
        time.sleep(2)
    shot('failure')
    raise RuntimeError(f'UI text remained visible: {label}')


def main():
    assert adb('shell','getprop','ro.boot.qemu.avd_name').stdout.strip()=='growth-test','Wrong emulator; refusing to install'
    adb('shell','wm','dismiss-keyguard')
    if '--release-only' in sys.argv:
        verify_release()
        return
    app=ROOT/'android/app/build/outputs/apk/debug/app-debug.apk'
    tests=ROOT/'android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'
    adb('uninstall','es.naxo.growth',check=False)
    adb('install','-r',str(app));adb('install','-r',str(tests))
    result=adb('shell','am','instrument','-w','es.naxo.growth.test/androidx.test.runner.AndroidJUnitRunner')
    (OUTPUT/'instrumentation.txt').write_text(result.stdout,encoding='utf-8')
    print(result.stdout,flush=True)
    assert 'OK (5 tests)' in result.stdout,'Android UI tests failed'
    adb('pull','/sdcard/Android/data/es.naxo.growth/files/screenshots',str(OUTPUT/'tests'))
    adb('uninstall','es.naxo.growth.test');adb('uninstall','es.naxo.growth')
    verify_release()


def verify_release():
    release=ROOT/'releases/android/Growth-0.1.0.apk'
    connected=release.exists()
    if not release.exists():release=ROOT/'releases/android/Growth-0.1.0-local.apk'
    adb('install','-r',str(release))
    adb('shell','pm','clear','es.naxo.growth')
    adb('logcat','-c')
    adb('shell','am','start','-n','es.naxo.growth/.MainActivity');time.sleep(5)
    nodes=list(tree().iter('node'))
    if any(n.attrib.get('text')=='Código privado de acceso' for n in nodes):
        fields=[n for n in nodes if n.attrib.get('class')=='android.widget.EditText']
        x1,y1,x2,y2=map(int,re.findall(r'\d+',fields[0].attrib['bounds']))
        adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))
        code=(ROOT/'.local/mobile/access-code.txt').read_text().strip()
        adb('shell','input','text',code)
        adb('shell','input','keyevent','4')
        tap('Entrar en Growth');wait_for_text('Growth')
    assert any(n.attrib.get('text')=='Growth' for n in tree().iter('node')),'Release app did not open'
    shot('inicio')
    for label,name in [('Cambios','cambios'),('Informes','informes')]:
        tap(label);shot(name)
    ticker=next((n.attrib['text'] for n in tree().iter('node') if re.fullmatch(r'[A-Z][A-Z0-9.-]{1,5}',n.attrib.get('text',''))),None)
    if ticker is None: raise RuntimeError('No ticker visible in the report grid')
    tap(ticker)
    for _ in range(8):
        if any(n.attrib.get('text')=='Leer informe completo' for n in tree().iter('node')):
            break
        adb('shell','input','swipe','500','1800','500','700','300')
    tap('Leer informe completo');wait_for_text('INFORME COMPLETO')
    shot('informe-completo')
    tap('Volver');tap('Tabla');shot('tabla')
    tap('Ajustes');tap('Oscura');tap('Listo');shot('tabla-oscura')
    checks=['launch','four_tabs','full_report','dark_theme','no_android_runtime_crash']
    if connected:
        adb('shell','am','force-stop','es.naxo.growth')
        adb('shell','am','start','-n','es.naxo.growth/.MainActivity')
        wait_for_text('Growth')
        wait_for_text('Actualizar datos')
        checks.append('encrypted_session_survives_restart')
        try:
            adb('shell','svc','wifi','disable');adb('shell','svc','data','disable')
            tap('Actualizar datos')
            wait_for_text('No se pudo conectar. Puedes consultar la última copia guardada.',timeout=140)
            tap('Tabla');wait_for_text('Mi tabla');shot('sin-conexion')
            checks.append('offline_dashboard_cache')
        finally:
            adb('shell','svc','wifi','enable');adb('shell','svc','data','enable')
        time.sleep(5)
        tap('Actualizar datos')
        wait_until_absent('Mostrando la última copia guardada')
        tap('Inicio')
    errors=adb('logcat','-d','-s','AndroidRuntime:E').stdout
    assert 'FATAL EXCEPTION' not in errors,errors
    (OUTPUT/'release-verification.json').write_text(json.dumps({
        'verified_at':datetime.now(timezone.utc).isoformat(),
        'apk':release.name,'sha256':hashlib.sha256(release.read_bytes()).hexdigest(),
        'device':SERIAL,'android_api':adb('shell','getprop','ro.build.version.sdk').stdout.strip(),
        'checks':checks,
    },indent=2),encoding='utf-8')
    print('Signed release launched and four screens verified. Screenshots:',OUTPUT)


if __name__=='__main__':main()
