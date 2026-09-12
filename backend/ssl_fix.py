"""Fix macOS/Linux Python SSL certificate store resolution."""

from __future__ import annotations

import os
import ssl


def apply() -> None:
    try:
        import certifi
    except ImportError:
        return

    ca = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", ca)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", ca)
    os.environ.setdefault("CURL_CA_BUNDLE", ca)

    # Ensure the default HTTPS context trusts certifi's bundle.
    ssl._create_default_https_context = (  # type: ignore[attr-defined]
        lambda *args, **kwargs: ssl.create_default_context(cafile=ca)
    )
