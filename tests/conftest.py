import logging
import pytest
import sys

from utils import get_client_partial

def pytest_addoption(parser):
    parser.addoption("--url", action="store", default="default name")

@pytest.fixture
def get_pulse(request):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    url = request.config.getoption("--url")
    return get_client_partial(url, "pytest", logger, "pulsecount")

@pytest.fixture
def get_varmax(request):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    url = request.config.getoption("--url")
    return get_client_partial(url, "pytest", logger, "varmax")
