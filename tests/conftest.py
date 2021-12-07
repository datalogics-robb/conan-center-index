import pytest


def pytest_addoption(parser):
    parser.addoption('--upload-to', help='upload built packages to the given remote')


@pytest.fixture
def upload_to(request):
    return request.config.getoption('--upload-to')
