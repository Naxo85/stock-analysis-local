"""Explicit CLI bridge, no external process/network in tests."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
import subprocess
import pytest
from google.auth.exceptions import RefreshError
from src.local_runner.publication_auth import validate_publication_auth,credentials_from_gcloud,storage_client
AUTH={'mode':'gcloud-cli','account':'reader@example.com','project':'example-project'}
@pytest.mark.parametrize('value',[None,{'mode':'adc'},AUTH])
def test_supported_explicit_modes(value):
    assert validate_publication_auth(value)['mode'] in ('adc','gcloud-cli')
@pytest.mark.parametrize('value',['gcloud-cli',{}, {'mode':'auto'}, {'mode':'adc','account':'x'},dict(AUTH,account='x&whoami@example.com'),dict(AUTH,account='x%HOME%@example.com'),dict(AUTH,account='reader@example.com\n'),dict(AUTH,project='x;bad'),dict(AUTH,token='never-persist')])
def test_invalid_auth_configuration(value):
    with pytest.raises(ValueError,match='invalid_publication_auth'):validate_publication_auth(value)
def test_cli_refresh_is_account_pinned_in_memory_and_repeated():
    credential=credentials_from_gcloud(AUTH['account'])
    with patch('src.local_runner.publication_auth.shutil.which',return_value='C:/sdk/gcloud.cmd'),patch('src.local_runner.publication_auth.subprocess.run',side_effect=[SimpleNamespace(returncode=0,stdout='token.first-1\n',stderr=''),SimpleNamespace(returncode=0,stdout='token.second-2\n',stderr='')]) as command:
        credential.refresh(None);assert credential.token=='token.first-1'
        credential.refresh(None);assert credential.token=='token.second-2'
    assert command.call_count==2
    assert '--account=reader@example.com' in command.call_args.args[0]
    assert command.call_args.kwargs['timeout']==45 and not command.call_args.kwargs.get('shell')
    assert 0<(credential.expiry-datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds()<=300
@pytest.mark.parametrize('bad',['','one two','token\nother','a\x00b','x'*8193,'ésecret'])
def test_invalid_token_never_leaks(bad):
    c=credentials_from_gcloud(AUTH['account'])
    with patch('src.local_runner.publication_auth.shutil.which',return_value='gcloud.cmd'),patch('src.local_runner.publication_auth.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=bad,stderr='secret-stderr')):
        with pytest.raises(RefreshError) as caught:c.refresh(None)
    assert str(caught.value)=='publication_gcloud_token_refresh_failed' and c.token is None
@pytest.mark.parametrize('result',[SimpleNamespace(returncode=1,stdout='secret-token',stderr='secret-stderr'),subprocess.TimeoutExpired('gcloud',45,output='secret-token')])
def test_refresh_errors_are_redacted(result):
    c=credentials_from_gcloud(AUTH['account'])
    with patch('src.local_runner.publication_auth.shutil.which',return_value='gcloud.cmd'),patch('src.local_runner.publication_auth.subprocess.run',side_effect=result if isinstance(result,Exception) else None,return_value=result):
        with pytest.raises(RefreshError) as caught:c.refresh(None)
    assert 'secret' not in str(caught.value)
def test_missing_cli_fails_without_fallback():
    with patch('src.local_runner.publication_auth.shutil.which',return_value=None):
        with pytest.raises(RefreshError,match='unavailable'):credentials_from_gcloud(AUTH['account']).refresh(None)
def test_adc_default_remains_unchanged():
    with patch('google.cloud.storage.Client') as client:
        storage_client();client.assert_called_once_with()
def test_explicit_mode_passes_project_and_credentials():
    with patch('google.cloud.storage.Client') as client:
        storage_client(AUTH)
    assert client.call_args.kwargs['project']=='example-project'
    assert type(client.call_args.kwargs['credentials']).__name__=='GcloudCliCredentials'
def test_policy_rejects_unknown_mode():
    import json
    from pathlib import Path
    from src.local_runner.adaptive_policy import validate_policy
    policy=json.loads(Path('config/codex_analysis.json').read_text());policy['publication_auth']={'mode':'auto'}
    with pytest.raises(ValueError,match='invalid_publication_auth'):validate_policy(policy)
def test_gcs_store_propagates_explicit_auth():
    from src.local_runner.publication_store import GcsStore
    with patch('src.local_runner.publication_auth.storage_client') as client:
        GcsStore('example-bucket',auth=AUTH)
    client.assert_called_once_with(AUTH)
@pytest.mark.parametrize('kind',['web','mobile','sheet'])
def test_all_consumers_reject_pointer_without_commit_timestamp(kind):
    from test_publication_consumers import fixture,modules,Client
    import json
    store=fixture.FakeStore();manifest=fixture.committed(store,'confirmed');manifest.pop('committed_at')
    store.objects['CAT/publication.json']=(json.dumps(manifest),99)
    reader,Mobile,_,Sheet,_,_=modules(Client(store))
    with pytest.raises(ValueError,match='not_committed'):
        if kind=='web':reader._read_latest_json('CAT')
        elif kind=='mobile':Mobile(storage_client=Client(store),sheets_session=object()).report_pair('CAT')
        else:Sheet('system',storage_client=Client(store)).index(('CAT',))
