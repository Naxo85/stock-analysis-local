"""Build a local review package; never deploy, fetch data, call models or publish."""
import argparse, hashlib, json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare(dest):
    dest=dest.resolve();allowed=(ROOT/'.tmp').resolve()
    if not dest.is_relative_to(allowed):raise ValueError('package_destination_must_be_repository_tmp')
    if dest.exists() and any(dest.iterdir()):raise ValueError('package_destination_must_be_empty')
    dest.mkdir(parents=True,exist_ok=True);manifest={'status':'prepared_not_deployed','source_revision':40,'bases_require_remote_reverification':True,'files':{},'source_bases':{}}
    for kind,names in [('raw',['main.py','market_sessions.py','price_path.py','technical_archive.py']),('slim',['main.py'])]:
        recorded=json.loads((ROOT/f'logs/deploy_origins39/{kind}-verified.json').read_text(encoding='utf-8'))
        image=recorded['spec']['template']['spec']['containers'][0]['image']
        if '@sha256:'not in image:raise ValueError('immutable_recorded_base_required')
        target=dest/kind;target.mkdir(exist_ok=True)
        for name in names:
            source=ROOT/f'gcp_functions/support_resistances_{kind}'/name;shutil.copyfile(source,target/name)
            manifest['files'][source.relative_to(ROOT).as_posix()]=sha(source)
        checks=' '.join('/app/'+n for n in names)
        docker='FROM '+image+'\n'+''.join('COPY '+n+' /app/'+n+'\n'for n in names)+'RUN python -m py_compile '+checks+'\n'
        if kind=='raw':docker+='RUN cd /app && python -c "import market_sessions, price_path, technical_archive"\n'
        (target/'Dockerfile').write_text(docker,encoding='utf-8')
        manifest['source_bases'][kind]={'image':image,'recorded_traffic':recorded['status']['traffic']}
    policy=json.loads((ROOT/'config/codex_analysis.json').read_text(encoding='utf-8'))
    policy.update(routing_revision=40,production_enabled=False,publication_protocol='manifest-v1',latest_attempt_publication_enabled=False,technical_archive_enabled=False)
    (dest/'candidate_policy40.json').write_text(json.dumps(policy,indent=2)+'\n',encoding='utf-8')
    manifest['candidate_policy_note']='Inactive candidate only; enable each effect after approved external verification. Models/efforts/ITV unchanged.'
    # Consumer and local changes are exact files, never an export of the dirty tree.
    baseline_path=ROOT/'.tmp/audit_execution_20261017/source_baseline.json'
    if not baseline_path.is_file():baseline_path=ROOT/'docs/audit_work_20261017/execution/results/source_baseline.json'
    baseline={k.replace('\\','/'):v for k,v in json.loads(baseline_path.read_text(encoding='utf-8')).items()}
    candidates=[]
    for prefix in ['src','gcp_services','gcp_functions/reports_reader','prompts']:
        candidates.extend(p for p in (ROOT/prefix).rglob('*') if p.is_file() and p.suffix in ('.py','.md') and '__pycache__'not in p.parts and not any(part.startswith('.') for part in p.relative_to(ROOT).parts))
    candidates.extend([ROOT/'android/app/src/main/java/es/naxo/growth/MainActivity.kt',ROOT/'requirements-manifest.txt'])
    for p in candidates:
        rel=p.relative_to(ROOT).as_posix();digest=sha(p)
        if baseline.get(rel)==digest:continue
        # Android has a two-line attempt-status change; it is included for review,
        # not packaged as a claimed built/signed/installable Android release.
        target=dest/'changes'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        manifest['files'][rel]=digest
    (dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    readme='''Local review snapshot only. Creating this package performs NO deployment or publication.
This snapshot is not evidence of deployed state; consult dated activation evidence.
1. Review manifest/hashes and obtain approval for named external actions.
2. Re-read current service specs, immutable digests, runtime/env/secrets/traffic.
   The source bases above are recorded 16-Oct evidence, not a current live assertion.
   If they differ, stop and rebase/review. Do not deploy stale repository Dockerfiles.
3. Deploy compatible reports_reader, mobile_api and controller consumers first;
   run staging checks with isolated test bucket/paths and pinned-version links.
   Keep current runtime, scopes, Sheet columns, scores, colors and hidden Res.
4. Build raw/slim overlays in these directories against verified active bases;
   test exact tagged revision without symbol first, then an explicitly approved
   technical capture. Verify closed sessions, quote/provider dates and coverage40.
5. Install optional requirements-manifest.txt on runner; verify CAS on an isolated
   test bucket with the explicitly selected publication authentication. Services use
   ADC normally. A local runner may use publication_auth mode gcloud-cli with the
   existing CLI account/project pinned and refresh handled in memory; no fallback,
   new keys or model/API substitution. Refresh IBKR naturally using the
   terminal-coverage adapter, no duplicate batch.
6. Enable routing40 only after source40 readiness and reviewed model tests.
   Enable manifest-v1 and attempt publication separately after all readers pass.
   candidate_policy40.json is deliberately production_enabled=false and inactive.
7. Technical research archiving is independently opt-in/off: raw
   EVALUATION_ARCHIVE_ENABLED plus new40 policy technical_archive_enabled.
   It reuses downloaded observations, does not add provider/model calls,
   and is stripped before mirrors/model context; archive failures are recorded
   separately and never replace financial admission checks. Verify output paths,
   byte budgets and coverage before enabling it in an authorized environment.
8. Observe next natural run; no automatic recovery of APP or historic report edits.
Rollback: do not revert to readers that ignore an existing manifest. Keep compatible
readers, revert algorithm revision only by an explicit reviewed activation. Versions
are immutable. A Sheet update is asynchronous; no global cross-ticker transaction.
'''
    (dest/'README.txt').write_text(readme,encoding='utf-8')
    for rel,digest in manifest['files'].items():
        if sha(ROOT/rel)!=digest:raise ValueError('source_changed_during_packaging:'+rel)
    return {'package':str(dest),'file_count':len(manifest['files']),'external_actions_performed':0}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT/'.tmp/audit_execution_20261017/review_package40_complete');args=ap.parse_args();print(json.dumps(prepare(args.output),indent=2))
