# Documentation claim auditor

This offline static checker compares documentation statements about sending local bytes with recognizable Python call sites. It scans the root README and Markdown below a docs directory, excluding fenced blocks; inline code counts. It parses source without executing it and excludes examples, fixtures, documentation, and symbolic links. Test evidence is reported separately. Exact phrases and listed denials determine matching; review findings in context.

```sh
file-upload-claim-audit audit . --json
file-upload-claim-audit audit . --fail-on medium --ignore vendor/
python3 -m file_upload_claim_audit --version
```

Findings use these identifiers:

```text
documented-file-upload-claim-false
documented-no-file-upload-claim-false
```

A missing production operation is high severity, or medium when found only in tests. A denial contradicted by production code is high severity. The default threshold is high; exit status 0 means the threshold was not met, 2 means it was met, and 1 indicates a usage or I/O error. JSON includes a verdict, findings, and messages. Verbose mode adds details. Ignore prefixes may be repeated.

The checker recognizes paired calls for S3, Google Cloud Storage and Azure Blob Storage, multipart calls using a files keyword, and specific generic method names. Construction alone or an unpaired provider method is insufficient. Each pair must appear in one module. A files keyword proves only a call site: its contents, size and destination cannot be verified, and local or mock endpoints count. Dead code counts; unresolved aliases and invalid Python are missed.

A form field, a deployment instruction, a path sent as JSON, or a server receiving multipart data may trigger a statement without establishing the checked operation. Review the source. String-based transfer, downloads, presigned URLs, local copies and subprocess commands are excluded. Calls without the files keyword and get, delete, head or options calls are excluded. The aiohttp FormData and manual urllib multipart paths are not traced.

API request auditing checks a broader transport shape: a post without files qualifies there, while a post with files can qualify for both. Web scraping fetches pages; download calls move data in the opposite direction. Database auditing checks database operations. Storage statements and generation statements use different wording and do not trigger this checker. Cache operations are not evidence. Importable API surface auditing checks names and arguments instead. Offline, privacy, timeout and server-sent event checks use transport calls for different questions.

Document extraction services, including Mindee, Document Intelligence, Veryfi, Document AI, Eden AI, Textract, LlamaParse, Nanonets, Docsumo, ABBYY Vantage, Rossum, Klippa, Parseur and Extend, are not evidence routes. Their parsing or submission calls concern extraction; Blob Storage and Cloud Storage are separate services. Opaque identifiers and generic endpoints do not establish the checked capability. Exact wording and the denial list limit the analysis; it is a static heuristic, not semantic judgment.
