from unittest.mock import MagicMock

import pytest

from papaya.context import PapayaContext
from papaya.iiif.image import ImageService
from papaya.source import SolrService, RepositoryService, Resource


@pytest.fixture
def papaya_context(get_mock_context, get_mock_resource):
    return get_mock_context(get_mock_resource(searchable=False))
