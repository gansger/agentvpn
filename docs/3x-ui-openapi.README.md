# 3x-ui OpenAPI Snapshot

`docs/3x-ui-openapi.json` is intentionally absent until it can be fetched from the actual
installed 3x-ui panel.

Configure the relevant `XUI_*` environment variables locally, then run:

```powershell
python infrastructure/scripts/fetch_xui_openapi.py
```

The script prints the snapshot SHA-256 digest. Record and review snapshot changes before
updating the typed adapter.

Do not commit credentials, session cookies, full panel responses containing secrets, or a
schema downloaded from an unrelated 3x-ui version.

