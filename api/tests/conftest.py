import os
import tempfile

os.environ.setdefault("DEEPSIGHT_DB", os.path.join(tempfile.gettempdir(), "deepsight-test.db"))
os.environ.setdefault("DEEPSIGHT_LIVE_TAP", "0")
os.environ.setdefault("DEEPSIGHT_IGNORE_CHAIN_FILE", "1")
