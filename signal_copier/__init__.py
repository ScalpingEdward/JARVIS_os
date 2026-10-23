

def fast_auron_url() -> None:
    """AURON_URL with "localhost" made 127.0.0.1. On Windows "localhost" tries IPv6 first and every call to
    AURON took 2.1 s instead of 0.02 -- the copiers' live numbers, their commands and the charts all waited
    (found 2026-10-23). Called once after the .env is loaded."""
    import os
    url = os.environ.get("AURON_URL")
    if url:
        os.environ["AURON_URL"] = url.replace("://localhost", "://127.0.0.1")
