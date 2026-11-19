"""Static documentation and source inspection."""
import ast
import os
import re
from pathlib import Path
from .phrases import FILEUPLOAD, NOFILEUPLOAD

GENERIC = frozenset('upload_to_s3 upload_to_cloud upload_to_storage upload_to_server upload_to_bucket upload_object put_file put_object send_file send_files post_file post_files upload_document upload_image upload_media upload_data upload_content transfer_file upload_files upload_to_azure upload_to_gcs upload_to_blob_storage upload_to_remote upload_via_multipart'.split())
UPLOAD_METHODS = frozenset('post put patch request'.split())

def normalize(text):
    text = text.lower().replace('’', "'")
    text = re.sub(r"n['’]t\b", ' not', text)
    return ' '.join(text.replace('-', ' ').split())

def patterns(phrases):
    return [(p, re.compile(r'(?<!\w)' + re.escape(p) + r'(?!\w)')) for p in sorted(phrases, key=lambda x: (-len(x), x))]

YES = patterns(FILEUPLOAD)
NO = patterns(NOFILEUPLOAD)

def claims(text):
    lines = []
    fence = None
    for line in text.splitlines():
        m = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2).strip():
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        lines.append(line)
    yes = no = False
    for para in re.split(r'\n\s*\n', '\n'.join(lines)):
        value = normalize(para)
        for _, pattern in NO:
            value, count = pattern.subn(' ', value)
            no |= bool(count)
        yes |= any(pattern.search(value) for _, pattern in YES)
    return yes, no

def evidence(text):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return False
    nodes = list(ast.walk(tree))
    shadows = {n.name for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    imports = {}
    for n in nodes:
        if isinstance(n, ast.Import):
            for a in n.names:
                imports[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                if a.name != '*':
                    imports[a.asname or a.name] = n.module + '.' + a.name
    bound = set()
    def names(target):
        if isinstance(target, ast.Name):
            bound.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts: names(item)
    for n in nodes:
        if isinstance(n, ast.Assign):
            for t in n.targets: names(t)
        elif isinstance(n, ast.AnnAssign): names(n.target)
        elif isinstance(n, (ast.With, ast.AsyncWith)):
            for item in n.items:
                if item.optional_vars: names(item.optional_vars)
    for name in shadows | bound:
        imports.pop(name, None)
    calls = [n for n in nodes if isinstance(n, ast.Call)]
    def route(f, target):
        if isinstance(f, ast.Name):
            return f.id not in shadows and imports.get(f.id) == target
        if isinstance(f, ast.Attribute) and f.attr == target.rsplit('.', 1)[-1] and f.attr not in shadows:
            base = f.value
            chain = []
            while isinstance(base, ast.Attribute):
                chain.append(base.attr)
                base = base.value
            if isinstance(base, ast.Name) and base.id not in shadows and base.id in imports:
                path = imports[base.id] + ('.' + '.'.join(reversed(chain)) if chain else '')
                prefix = target.rsplit('.', 1)[0]
                return path == prefix or path.startswith(prefix + '.')
        return False
    def attr(call, names):
        return isinstance(call.func, ast.Attribute) and call.func.attr in names and call.func.attr not in shadows
    def has(target):
        return any(route(c.func, target) for c in calls)
    def service(c):
        return (bool(c.args) and isinstance(c.args[0], ast.Constant) and c.args[0].value == 's3') or any(k.arg == 'service_name' and isinstance(k.value, ast.Constant) and k.value.value == 's3' for k in c.keywords)
    s3 = any(service(c) and (route(c.func, 'boto3.client') or route(c.func, 'boto3.resource')) for c in calls)
    if s3 and any(attr(c, {'upload_file', 'upload_fileobj'}) for c in calls): return True
    blob = has('google.cloud.storage.Blob') or any(attr(c, {'blob'}) for c in calls)
    if blob and any(attr(c, {'upload_from_filename', 'upload_from_file'}) for c in calls): return True
    azure = any(has('azure.storage.blob.' + name) for name in ('BlobClient', 'ContainerClient')) or any(attr(c, {'get_blob_client'}) for c in calls)
    if azure and any(attr(c, {'upload_blob'}) for c in calls): return True
    multipart = [c for c in calls if any(k.arg == 'files' for k in c.keywords)]
    if any(route(c.func, lib + '.' + method) for c in multipart for lib in ('requests', 'httpx') for method in UPLOAD_METHODS): return True
    client = any(has(target) for target in ('requests.Session', 'httpx.Client', 'httpx.AsyncClient'))
    if client and any(attr(c, UPLOAD_METHODS) for c in multipart): return True
    for c in calls:
        f = c.func
        if isinstance(f, ast.Attribute) and f.attr in GENERIC and f.attr not in shadows: return True
        if isinstance(f, ast.Name) and f.id not in shadows and imports.get(f.id, '').rsplit('.', 1)[-1] in GENERIC: return True
    return False

def audit(root='.', ignore=()):
    root = Path(root)
    if root.is_symlink() or not root.is_dir(): raise OSError('repository is not a directory: ' + str(root))
    yes = no = prod = test = False
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=lambda e: (_ for _ in ()).throw(e)):
        base = Path(directory)
        dirs[:] = [d for d in dirs if not (base / d).is_symlink() and not any((base / d).relative_to(root).as_posix().startswith(p) for p in ignore)]
        for filename in files:
            path = base / filename
            rel = path.relative_to(root)
            if path.is_symlink() or any(rel.as_posix().startswith(p) for p in ignore): continue
            parts = rel.parts
            if (len(parts) == 1 and filename == 'README.md') or ('docs' in parts[:-1] and filename.endswith('.md')):
                y, n = claims(path.read_text(encoding='utf-8')); yes |= y; no |= n
            if filename.endswith('.py') and not set(parts[:-1]) & {'fixtures', 'docs', 'examples'}:
                found = evidence(path.read_text(encoding='utf-8'))
                is_test = 'tests' in parts[:-1] or filename.startswith('test_') or filename.endswith('_test.py')
                if is_test: test |= found
                else: prod |= found
    findings = []
    if yes and not prod:
        findings.append({'id': 'documented-file-upload-claim-false', 'severity': 'MEDIUM' if test else 'HIGH', 'message': 'Documented capability has evidence only in tests.' if test else 'Documented capability has no production evidence.'})
    if no and prod:
        findings.append({'id': 'documented-no-file-upload-claim-false', 'severity': 'HIGH', 'message': 'Documented denial conflicts with production evidence.'})
    return {'verdict': 'FAIL' if findings else 'PASS', 'findings': findings}
