"""Prepare a private headless test device under .local; never alters user devices."""
import json
import os
from pathlib import Path
import subprocess
from android_toolchain import install, TOOLS

env=install()
config=json.loads((TOOLS/'environment.json').read_text())
sdk=Path(config['sdk'])
manager=sdk/'cmdline-tools/19.0/bin/sdkmanager.bat'
env['ANDROID_AVD_HOME']=str(TOOLS/'avd')
env['ANDROID_USER_HOME']=str(TOOLS/'user-home')
Path(env['ANDROID_AVD_HOME']).mkdir(exist_ok=True)
Path(env['ANDROID_USER_HOME']).mkdir(exist_ok=True)
image='system-images;android-35;default;x86_64'
subprocess.run([str(manager),f'--sdk_root={sdk}','emulator',image],input='y\n'*20,text=True,env=env,check=True)
avd=sdk/'cmdline-tools/19.0/bin/avdmanager.bat'
if not (TOOLS/'avd/growth-test.ini').exists():
    subprocess.run([str(avd),'create','avd','--name','growth-test','--package',image,'--device','pixel_6'],input='no\n',text=True,env=env,check=True)
subprocess.run([str(sdk/'emulator/emulator.exe'),'-accel-check'],env=env)
print('Private test emulator prepared',flush=True)
