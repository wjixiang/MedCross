from ukb_mcp.config import get_settings
from pprint import pprint

def test_settings():
    settings = get_settings()
    pprint(settings)
    assert True

test_settings()