"""Reproducible personal signed APK, with the signing key kept outside source."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from android_toolchain import TOOLS, ROOT, install


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--task',default='assembleRelease')
    parser.add_argument('--offline',action='store_true',help='Bundle the verified private snapshot; no server required')
    args=parser.parse_args()
    env=install()
    config=json.loads((TOOLS/'environment.json').read_text())
    personal=ROOT/'.local/mobile';personal.mkdir(exist_ok=True)
    password_file=personal/'signing-password.txt'
    if not password_file.exists(): password_file.write_text(secrets.token_urlsafe(32))
    password=password_file.read_text().strip()
    key_file=personal/'growth-release.jks'
    env['GROWTH_KEYSTORE']=str(key_file)
    env['GROWTH_KEY_PASSWORD']=password
    if not key_file.exists():
        subprocess.run([str(Path(config['java'])/'bin/keytool.exe'),'-genkeypair','-keystore',str(key_file),'-storepass:env','GROWTH_KEY_PASSWORD','-keypass:env','GROWTH_KEY_PASSWORD','-alias','growth','-keyalg','RSA','-keysize','3072','-validity','10000','-dname','CN=Growth Personal, OU=Personal Apps, O=Growth, C=ES'],check=True,env=env)
    project=ROOT/'android'
    (project/'local.properties').write_text('sdk.dir='+str(Path(config['sdk'])).replace('\\','/').replace(':','\\:')+'\n',newline='\n')
    deployment=personal/'deployment.json'
    url=json.loads(deployment.read_text())['url'] if deployment.exists() else ''
    offline=args.offline or not url
    if offline and not (personal/'offline/dashboard.json').exists():
        raise RuntimeError('Run verify_mobile_data.py to prepare the private offline snapshot first')
    command=[str(Path(config['gradle'])/'bin/gradle.bat'),'--no-daemon','--console=plain',f'-PgrowthApiUrl={url}',f'-PgrowthOffline={str(offline).lower()}',*args.task.split(',')]
    print('Building Android:',args.task,flush=True)
    subprocess.run(command,cwd=project,env=env,check=True)
    apk=project/'app/build/outputs/apk/release/app-release.apk'
    if 'assembleRelease' in args.task.split(',') and apk.exists():
        release=ROOT/'releases/android';release.mkdir(parents=True,exist_ok=True)
        destination=release/('Growth-0.1.0-local.apk' if offline else 'Growth-0.1.0.apk');shutil.copy2(apk,destination)
        subprocess.run([str(Path(config['sdk'])/'build-tools/35.0.0/apksigner.bat'),'verify','--verbose',str(destination)],check=True,env=env)
        destination.with_suffix('.sha256').write_text(hashlib.sha256(destination.read_bytes()).hexdigest()+'  '+destination.name+'\n')
        instructions = ('Growth 0.1.0 - Android 8 o posterior\n\n'
            '1. Copia la APK al telefono y abrela.\n'
            '2. Si Android lo solicita, permite la instalacion desde la aplicacion con la que has abierto el fichero.\n\n')
        if offline:
            snapshot=json.loads((personal/'offline/dashboard.json').read_text(encoding='utf-8'))
            instructions += f'Edicion local: datos verificados el {snapshot["generated_at"]}.\nIncluye {len(snapshot["stocks"])} empresas y sus informes. No requiere codigo ni conexion.\nNo actualiza cotizaciones o informes; muestra la fecha de cada dato.\nLa APK contiene datos privados de tu sistema: uso personal.\n'
        else:
            instructions += 'Edicion conectada: introduce una vez el codigo privado de .local/mobile/access-code.txt.\nLas actualizaciones conservan fecha del precio y del analisis por separado.\n'
        (release/'INSTALAR.txt').write_text(instructions,encoding='utf-8')
        print('Signed APK:',destination,flush=True)


if __name__=='__main__':main()
