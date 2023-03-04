import os
import sys

path = os.path.join(os.path.dirname(os.path.realpath(__file__)),"../../../.")
sys.path.append(path)

def test_app():
    os.environ["FRONTEND_CORS_URL"] = "testurl"
    import app