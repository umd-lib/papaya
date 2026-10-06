import pytest


@pytest.fixture
def papaya_context(get_mock_context, get_mock_resource):
    return get_mock_context(get_mock_resource(searchable=False))
