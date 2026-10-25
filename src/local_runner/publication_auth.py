"""Explicit storage authentication using ADC or the already authenticated CLI.

No fallback, key files, token persistence or model API use. A CLI account is
pinned by policy; errors never include subprocess output containing credentials.
"""
from datetime import datetime, timedelta, timezone
import os
import re
import shutil
import subprocess


def validate_publication_auth(value):
    if value is None:
        return {'mode': 'adc'}
    if not isinstance(value, dict):
        raise ValueError('invalid_publication_auth')
    if value == {'mode': 'adc'}:
        return dict(value)
    if (set(value) != {'mode', 'account', 'project'} or value.get('mode') != 'gcloud-cli'
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', str(value.get('account', '')))
            or not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]', str(value.get('project', '')))):
        raise ValueError('invalid_publication_auth')
    return dict(value)


def credentials_from_gcloud(account):
    from google.auth.credentials import Credentials
    from google.auth.exceptions import RefreshError
    validate_publication_auth({'mode': 'gcloud-cli', 'account': account, 'project': 'validation-project'})
    class GcloudCliCredentials(Credentials):
        def refresh(self, request):
            self.token = None
            self.expiry = None
            executable = shutil.which('gcloud.cmd' if os.name == 'nt' else 'gcloud')
            if not executable:
                raise RefreshError('publication_gcloud_unavailable')
            command = [executable, 'auth', 'print-access-token', '--account='+account, '--quiet']
            if os.name == 'nt':
                command = ['cmd.exe', '/d', '/c', *command]
            try:
                result = subprocess.run(command, capture_output=True, text=True,
                    encoding='utf-8', timeout=45, check=False,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0)
            except (OSError, subprocess.SubprocessError):
                raise RefreshError('publication_gcloud_token_refresh_failed') from None
            token = result.stdout.strip()
            if result.returncode or not token or len(token) > 8192 or re.fullmatch(r'[A-Za-z0-9._~+/-]+={0,2}', token) is None:
                raise RefreshError('publication_gcloud_token_refresh_failed') from None
            self.token = token
            # Conservative refresh schedule, not a claim about the server token's
            # actual expiry. AuthorizedSession also refreshes on an auth rejection.
            self.expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5)
    return GcloudCliCredentials()


def storage_client(auth=None):
    from google.cloud import storage
    selected = validate_publication_auth(auth)
    if selected['mode'] == 'adc':
        return storage.Client()
    return storage.Client(project=selected['project'],
                          credentials=credentials_from_gcloud(selected['account']))
