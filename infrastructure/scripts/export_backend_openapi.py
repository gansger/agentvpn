"""Export the current AGentVPN backend OpenAPI document."""

from __future__ import annotations

import json
from pathlib import Path

from apps.api.agentvpn_api.main import create_app

OUTPUT_PATH = Path("docs/backend-openapi.json")


def main() -> None:
    document = create_app().openapi()
    OUTPUT_PATH.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Backend OpenAPI written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
