import json
import tempfile
import unittest
from pathlib import Path
from file_upload_claim_audit.audit import audit, claims, evidence, GENERIC
from file_upload_claim_audit.phrases import FILEUPLOAD, NOFILEUPLOAD
from file_upload_claim_audit.__main__ import main

EXPECTED_YES = ('uploads files', 'upload files', 'uploads a file', 'upload a file', 'uploads file', 'upload file', 'file upload support', 'file uploads support', 'uploads files to the cloud', 'upload files to the cloud', 'uploads files to s3', 'upload files to s3', 'uploads files to storage', 'upload files to storage', 'uploads files to the server', 'upload files to the server', 'uploads files to a server', 'upload files to a server', 'uploads files to a bucket', 'upload files to a bucket', 'uploads files to cloud storage', 'upload files to cloud storage', 'uploads files to remote storage', 'upload files to remote storage', 'supports file upload', 'supports file uploads', 'supports uploading files', 'supports uploading a file', 'file upload feature', 'file uploads feature', 'file upload functionality', 'file upload capability', 'file upload capabilities', 'file upload', 'file uploads', 'uploads files to aws', 'upload files to aws', 'uploads files to azure', 'upload files to azure', 'uploads files to google cloud', 'upload files to google cloud', 'uploads files to gcs', 'upload files to gcs', 'multipart file upload', 'multipart file uploads', 'upload files via multipart', 'uploads files via multipart', 'sends files to the server', 'send files to the server', 'transfers files to the server')
EXPECTED_NO = ('does not upload files', 'never uploads files', 'does not upload a file', 'never uploads a file', 'does not upload file', 'never uploads file', 'no file upload support', 'no file uploads support', 'does not support file upload', 'never supports file upload', 'does not support file uploads', 'never supports file uploads', 'no file upload feature', 'no file upload functionality', 'no file upload capability', 'does not upload files to the cloud', 'never uploads files to the cloud', 'does not upload files to s3', 'never uploads files to s3', 'does not upload files to the server', 'never uploads files to the server', 'no file upload', 'no file uploads', 'does not send files to the server')

class AuditTests(unittest.TestCase):
    def test_phrase_oracle(self):
        self.assertEqual(FILEUPLOAD, EXPECTED_YES)
        self.assertEqual(NOFILEUPLOAD, EXPECTED_NO)
        for phrase in EXPECTED_YES: self.assertEqual(claims(phrase), (True, False))
        for phrase in EXPECTED_NO: self.assertEqual(claims(phrase), (False, True))
    def test_routes(self):
        cases = ["import boto3; boto3.client('s3'); x.upload_file()", "import boto3; boto3.client('s3'); x.upload_fileobj()", "import boto3; boto3.resource('s3'); x.upload_file()", "from boto3 import client as c; c(service_name='s3'); x.upload_file()", "import google.cloud.storage; google.cloud.storage.Blob(); x.upload_from_filename()", "x.blob(); x.upload_from_file()", "from google.cloud.storage import Blob as B; B(); x.upload_from_filename()", "import azure.storage.blob; azure.storage.blob.BlobClient(); x.upload_blob()", "from azure.storage.blob import ContainerClient; ContainerClient(); x.upload_blob()", "x.get_blob_client(); x.upload_blob()"]
        for lib in ('requests', 'httpx'):
            for method in ('post','put','patch','request'):
                cases.append('import '+lib+'; '+lib+'.'+method+'(files={})')
            cases.append('from '+lib+' import post as p; p(files={})')
        for lib, cls, method in [('requests','Session','post'),('requests','Session','put'),('httpx','Client','post'),('httpx','AsyncClient','put')]:
            cases.append('import '+lib+'; '+lib+'.'+cls+'(); x.'+method+'(files={})')
        cases += ['x.'+name+'()' for name in GENERIC]
        cases += ['from x import upload_to_s3 as u; u()']
        for code in cases:
            with self.subTest(code=code): self.assertTrue(evidence(code))
    def test_non_evidence(self):
        cases = ['import boto3', "import boto3; boto3.client('s3')", 'x.upload_file()', 'x.upload_fileobj()', 'x.upload_from_filename()', 'x.upload_from_file()', 'x.upload_blob()', 'x.upload_from_string()', 'x.download_file()', 'x.download_fileobj()', 'x.get_object()', "open('x').read()", 'import shutil; shutil.copy(a,b)', 'import shutil; shutil.move(a,b)', 'import os; os.rename(a,b)', 'x.generate_presigned_url()', 'x.generate_presigned_post()', 'import requests; requests.post(x)', 'import requests; requests.put(x)', 'import requests; requests.Session(); x.post(x)', 'import httpx; httpx.post(x)', 'import requests; requests.get(x, files={})', 'def upload_file(): pass\nupload_file()', "import subprocess; subprocess.run(['aws','s3','cp'])", "import subprocess; subprocess.run(['gsutil'])", "'upload'", 'def send_file(): pass\nx.send_file()', 'import botocore; botocore.client("s3"); x.upload_file()', 'from azure.storage.blob import BlobClient; BlobClient()', 'from azure.storage.blob import ContainerClient; ContainerClient()', 'import requests; requests.post = x']
        for code in cases:
            with self.subTest(code=code): self.assertFalse(evidence(code))
    def test_documents_and_findings(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); readme=root/'README.md'
            readme.write_text('uploads files')
            self.assertEqual(audit(root)['findings'][0]['severity'], 'HIGH')
            self.assertEqual(main(['audit', d]), 2)
            (root/'tests').mkdir(); (root/'tests/test_x.py').write_text('x.send_file()')
            self.assertEqual(audit(root)['findings'][0]['severity'], 'MEDIUM')
            self.assertEqual(main(['audit', d]), 0); self.assertEqual(main(['audit', d, '--fail-on', 'medium']), 2)
            (root/'app.py').write_text('x.send_file()')
            self.assertEqual(audit(root)['verdict'], 'PASS')
            readme.write_text('does not upload files')
            self.assertEqual(audit(root)['findings'][0]['id'], 'documented-no-file-upload-claim-false')
            (root/'app.py').unlink(); self.assertEqual(audit(root)['verdict'], 'PASS')
            readme.write_text('```\nuploads files\n```'); self.assertEqual(audit(root)['verdict'], 'PASS')
            readme.write_text('`uploads files`'); self.assertEqual(audit(root)['findings'][0]['severity'], 'MEDIUM')
    def test_split_and_ignore(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'README.md').write_text('uploads files'); (p/'a.py').write_text("import boto3; boto3.client('s3')"); (p/'b.py').write_text('x.upload_file()')
            self.assertEqual(audit(p)['verdict'], 'FAIL')
            (p/'b.py').write_text('x.send_file()'); self.assertEqual(audit(p)['verdict'], 'PASS')
            self.assertEqual(audit(p, ['b.py'])['verdict'], 'FAIL')
    def test_vendor_and_shadow_exclusions(self):
        cases = ['mindee.parse(InvoiceV4)', 'x.begin_analyze_document("prebuilt-layout")', 'veryfi.Client()', 'documentai.process_document()', 'textract.analyze_document()', 'eden.universal_ai()', 'llamaparse.parse()', 'nanonets.ocr(model_id="opaque")', 'docsumo.upload()', 'import requests; requests = x; requests.post(files={})', 'from requests import post; post = x; post(files={})', 'from requests import post; with x as post: pass\npost(files={})']
        for code in cases:
            with self.subTest(code=code): self.assertFalse(evidence(code))
    def test_symlinks_json_and_entrypoints(self):
        import os, subprocess, sys
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            root = Path(d); (root/'README.md').write_text('uploads files')
            target = Path(outside)/'external.py'; target.write_text('x.send_file()')
            (root/'link.py').symlink_to(target)
            self.assertEqual(audit(root)['verdict'], 'FAIL')
            env = dict(os.environ); env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1]/'src')
            r = subprocess.run([sys.executable, '-m', 'file_upload_claim_audit', 'audit', d, '--json'], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 2)
            result = json.loads(r.stdout)
            self.assertEqual(result['verdict'], 'FAIL')
            self.assertTrue(result['findings'][0]['message'])
    def test_version(self):
        with self.assertRaises(SystemExit) as e: main(['--version'])
        self.assertEqual(e.exception.code, 0)

if __name__ == '__main__': unittest.main()
