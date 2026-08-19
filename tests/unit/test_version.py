"""Release metadata consistency tests."""

from importlib.metadata import version

import daktela


def test_public_version_matches_package_metadata() -> None:
    assert daktela.__version__ == "1.1.0"
    assert version("daktela") == daktela.__version__
