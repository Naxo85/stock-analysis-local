"""Install the signed APK on the private emulator without erasing its login."""
from pathlib import Path
from android_toolchain import ROOT
from test_android_emulator import adb, shot, tap, wait_for_text


def main():
    avd=adb('shell','getprop','ro.boot.qemu.avd_name').stdout.strip()
    assert avd=='growth-test','Wrong emulator; refusing to update'
    apk=ROOT/'releases/android/Growth-0.1.0.apk'
    assert apk.exists(),'Signed connected APK is missing'
    result=adb('install','-r',str(apk))
    assert 'Success' in result.stdout,result.stdout
    adb('shell','am','force-stop','es.naxo.growth')
    adb('shell','am','start','-n','es.naxo.growth/.MainActivity')
    wait_for_text('Growth')
    shot('inicio')
    for label,name in [('Cambios','cambios'),('Informes','informes'),('Tabla','tabla')]:
        tap(label);shot(name)
    tap('Inicio')
    print('Updated the visible emulator without clearing the private session.')


if __name__=='__main__': main()
