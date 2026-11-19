"""Open URLs in Chrome under the ZizAI web allowlist."""
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit, urlunsplit

import pandas as pd
import yaml


POLICY_PATH = Path(__file__).resolve().with_name('security_policies.yml')
SCHEMES = {'http', 'https'}
DNS_LABEL = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z')
IPV4_LABEL = re.compile(r'(?:0x[0-9a-f]+|[0-9]+)\Z')
MAX_POLICY_BYTES = 1024 * 1024


def _domain(host):
    try:
        name = (host or '').removesuffix('.').encode('idna').decode('ascii').lower()
    except UnicodeError as error:
        raise ValueError('ドメイン名が不正です。') from error
    labels = name.split('.')
    if (len(labels) < 2 or len(name) > 253 or name.endswith('.localhost')
            or all(IPV4_LABEL.fullmatch(label) for label in labels)
            or not all(DNS_LABEL.fullmatch(label) for label in labels)):
        raise ValueError('ドメイン名が不正です。')
    return name


def _split_target(url):
    if not isinstance(url, str) or not url.strip():
        raise ValueError('URLを指定してください。')
    text = url.strip()
    if any(char == '\\' or char.isspace() or ord(char) < 32 or ord(char) == 127 for char in text):
        raise ValueError('URLに使用できない文字が含まれています。')
    parts = urlsplit(text)
    if parts.scheme not in SCHEMES or parts.username is not None or parts.password is not None:
        raise ValueError('HTTPまたはHTTPSのURLを指定してください。')
    host = _domain(parts.hostname)
    port = parts.port
    path = parts.path or '/'
    decoded_path = unquote(path, errors='strict')
    if ('\\' in decoded_path or any(ord(char) < 32 or ord(char) == 127 for char in decoded_path)
            or any(segment in ('.', '..') for segment in decoded_path.split('/'))):
        raise ValueError('URLのパスが不正です。')
    authority = f'{host}:{port}' if port is not None else host
    return host, path, urlunsplit((parts.scheme, authority, path, parts.query, parts.fragment))


def _load_rules():
    try:
        with POLICY_PATH.open('rb') as stream:
            contents = stream.read(MAX_POLICY_BYTES + 1)
        if len(contents) > MAX_POLICY_BYTES:
            raise ValueError('許可リストのファイルが大きすぎます。')
        config = yaml.safe_load(contents)
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ValueError('Chromeの許可リスト security_policies.yml を確認してください。') from error
    web = config.get('web') if isinstance(config, dict) else None
    rules = web.get('allowlist') if isinstance(web, dict) else None
    if not isinstance(rules, list) or not rules:
        raise ValueError('Chromeの許可リストに開けるURLを設定してください。')
    return rules


def _matches(rule, host, path):
    if not isinstance(rule, dict) or not isinstance(rule.get('domain'), str):
        return False
    domain = rule['domain'].strip()
    prefixes = rule.get('path_prefixes', ['/'])
    if not isinstance(prefixes, list) or not prefixes or not all(
        isinstance(prefix, str) and prefix.startswith('/') for prefix in prefixes
    ):
        return False
    try:
        explicit_scheme = '://' in domain
        if domain.startswith('//'):
            return False
        parsed = urlsplit(domain if explicit_scheme else '//' + domain)
        if ((explicit_scheme and parsed.scheme not in SCHEMES) or parsed.username is not None
                or parsed.port is not None or parsed.netloc.endswith(':')):
            return False
        label = parsed.hostname or ''
        wildcard = label.startswith('*.')
        rule_host = _domain(label[2:] if wildcard else label)
    except ValueError:
        return False
    if wildcard:
        suffix = '.' + rule_host
        if not host.endswith(suffix):
            return False
        subdomain = host[:-len(suffix)]
        if not subdomain or '.' in subdomain:
            return False
    elif host != rule_host:
        return False
    return any(path.startswith(prefix) for prefix in prefixes)


def _find_chrome():
    if os.name != 'nt':
        raise OSError('Chromeで開く機能はWindowsで利用できます。')
    for variable in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        root = os.environ.get(variable)
        if root:
            candidate = Path(root) / 'Google/Chrome/Application/chrome.exe'
            if candidate.is_file():
                return candidate
    for entry in os.environ.get('PATH', '').split(os.pathsep):
        directory = Path(entry.strip('"'))
        if directory.is_absolute() and directory != Path.cwd():
            candidate = directory / 'chrome.exe'
            if candidate.is_file():
                return candidate
    raise FileNotFoundError('Google Chrome が見つかりません。')


def open_in_chrome(url):
    """Request a Chrome navigation to an allowed URL."""
    host, path, target = _split_target(url)
    if not any(_matches(rule, host, path) for rule in _load_rules()):
        raise ValueError('指定したURLはChromeの許可リストにありません。')
    chrome = _find_chrome()
    subprocess.Popen([str(chrome), target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return pd.DataFrame([{
        'status': 'launch_requested',
        'action': 'open_in_chrome',
        'url': target,
        'browser': 'chrome',
    }])
