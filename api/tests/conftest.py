import os
import tempfile
import pytest

_test_root = tempfile.TemporaryDirectory(prefix="deepsight-tests-")
os.environ["DEEPSIGHT_DATA_DIR"] = _test_root.name
os.environ["DEEPSIGHT_DB"] = os.path.join(_test_root.name, "test.db")
os.environ["DATABASE_URL"] = "sqlite:///" + os.environ["DEEPSIGHT_DB"]
os.environ["DEEPSIGHT_RELAY_ENABLED"] = "0"
os.environ["DEEPSIGHT_LIVE_TAP"] = "0"
os.environ["DEEPSIGHT_IGNORE_CHAIN_FILE"] = "1"
os.environ.pop("DEEPSIGHT_CONTRACT_ADDRESS", None)
os.environ["DEEPSIGHT_REVIEWERS"] = "0x" + "1" * 40


@pytest.fixture(autouse=True)
def authenticated_test_user():
    from api.main import app
    from api.auth import current_user, optional_user
    from api.db import Base, engine
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    app.dependency_overrides[current_user] = lambda: "0x" + "1" * 40
    app.dependency_overrides[optional_user] = lambda: "0x" + "1" * 40
    yield
    app.dependency_overrides.clear()
