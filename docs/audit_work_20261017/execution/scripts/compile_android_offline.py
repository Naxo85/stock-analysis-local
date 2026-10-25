"""Compile only the changed Android consumer in a local copy, no signing/install/network."""
import os,json,shutil,subprocess,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'.tmp/audit_execution_20261017';project=OUT/'android_compile_copy'
if project.exists():raise RuntimeError('isolated_compile_destination_exists')
project.mkdir();config=json.loads((ROOT/'.local/android/environment.json').read_text())
for name in ['build.gradle.kts','settings.gradle.kts','gradle.properties','local.properties']:shutil.copyfile(ROOT/'android'/name,project/name)
(project/'app').mkdir();shutil.copyfile(ROOT/'android/app/build.gradle.kts',project/'app/build.gradle.kts');shutil.copytree(ROOT/'android/app/src',project/'app/src')
env=dict(os.environ,JAVA_HOME=config['java'],ANDROID_HOME=config['sdk'],ANDROID_SDK_ROOT=config['sdk'],GRADLE_USER_HOME=str(ROOT/'.local/android/gradle-cache'))
env['PATH']=str(Path(config['java'])/'bin')+os.pathsep+env.get('PATH','')
for key in ['GROWTH_KEYSTORE','GROWTH_KEY_PASSWORD']:env.pop(key,None)
command=[str(Path(config['gradle'])/'bin/gradle.bat'),'--offline','--no-daemon','--console=plain','-PgrowthOffline=false','-PgrowthApiUrl=','compileDebugKotlin','testDebugUnitTest']
start=time.monotonic()
with (OUT/'android_compile_offline.log').open('w',encoding='utf8')as log:
 result=subprocess.run(command,cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=600)
evidence={'exit_code':result.returncode,'seconds':round(time.monotonic()-start,2),'tasks':['compileDebugKotlin','testDebugUnitTest'],'offline':True,'signed':False,'installed':False,'private_offline_assets':False,'source_sha256':hashlib.sha256((ROOT/'android/app/src/main/java/es/naxo/growth/MainActivity.kt').read_bytes()).hexdigest()}
(OUT/'android_compile_result.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf8');print(json.dumps(evidence,indent=2));raise SystemExit(result.returncode)
