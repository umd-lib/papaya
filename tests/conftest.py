from unittest.mock import MagicMock

import pytest

from papaya.context import PapayaContext
from papaya.iiif.image import ImageService
from papaya.source import Resource, SolrService, RepositoryService


@pytest.fixture
def get_mock_resource():
    def _get_resource(searchable=False):
        return MagicMock(
            spec=Resource,
            label='Foobar',
            description='Testing manifest',
            metadata={},
            date='2026-05-22',
            license='CC-BY-NC-SA',
            page_uris=[
                'http://example.com/page1',
                'http://example.com/page2',
                'http://example.com/page3',
            ],
            is_searchable=searchable,
        )
    return _get_resource


@pytest.fixture
def get_mock_context():
    def _get_context(resource=None):
        ctx = MagicMock(
            spec=PapayaContext,
            solr_service=MagicMock(spec=SolrService),
            repo_service=MagicMock(spec=RepositoryService),
            image_service=MagicMock(
                spec=ImageService,
                thumbnail_width=250,
            ),
            endpoint_url='http://example.com/manifests',
            logo_url='http://example.com/logo',
        )
        if resource is not None:
            ctx.get_resource.return_value = resource
        return ctx
    return _get_context
