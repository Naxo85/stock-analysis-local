"""Launch the private emulator; --visible --open-app opens Growth for the user."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from android_toolchain import TOOLS

parser=argparse.ArgumentParser()
parser.add_argument('--visible',action='store_true',help='Show the Android emulator window')
parser.add_argument('--open-app',action='store_true',help='Open the installed Growth app after boot')
args=parser.parse_args()
config=json.loads((TOOLS/'environment.json').read_text())
sdk=Path(config['sdk'])
env=dict(os.environ,JAVA_HOME=config['java'],ANDROID_HOME=str(sdk),ANDROID_SDK_ROOT=str(sdk),ANDROID_AVD_HOME=str(TOOLS/'avd'),ANDROID_USER_HOME=str(TOOLS/'user-home'))
adb=str(sdk/'platform-tools/adb.exe')
serial='emulator-5580'
probe=subprocess.run([adb,'-s',serial,'get-state'],capture_output=True,text=True)
if probe.returncode:
    log=(TOOLS/'emulator.log').open('w')
    command=[str(sdk/'emulator/emulator.exe'),'-avd','growth-test','-port','5580','-no-audio','-no-snapshot','-gpu','swiftshader_indirect','-memory','2048','-cores','2','-no-boot-anim','-timezone','Europe/Madrid']
    if not args.visible: command.append('-no-window')
    process=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (TOOLS/'emulator.pid').write_text(str(process.pid))
    print('Started private '+('visible' if args.visible else 'headless')+' emulator',process.pid,flush=True)
for _ in range(80):
    result=subprocess.run([adb,'-s',serial,'shell','getprop','sys.boot_completed'],capture_output=True,text=True,timeout=10)
    if result.stdout.strip()=='1':
        for setting in ['window_animation_scale','transition_animation_scale','animator_duration_scale']:
            subprocess.run([adb,'-s',serial,'shell','settings','put','global',setting,'0'],check=True)
        subprocess.run([adb,'-s',serial,'shell','wm','dismiss-keyguard'],check=True)
        if args.open_app:
            name=subprocess.run([adb,'-s',serial,'shell','getprop','ro.boot.qemu.avd_name'],capture_output=True,text=True,check=True).stdout.strip()
            if name != 'growth-test': raise RuntimeError('Unexpected emulator; refusing to launch app')
            subprocess.run([adb,'-s',serial,'shell','am','start','-n','es.naxo.growth/.MainActivity'],check=True)
        print('Private Android emulator booted:',serial,flush=True)
        break
    time.sleep(3)
else: raise RuntimeError('Android emulator did not finish booting; inspect .local/android/emulator.log')
