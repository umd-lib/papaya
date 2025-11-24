import logging
import re
from collections.abc import Iterable, Mapping
from typing import NamedTuple
from urllib.parse import parse_qsl
from uuid import uuid4

import jq
import pysolr

logger = logging.getLogger(__name__)


def format_language_tags(values: Iterable[str]):
    for value in values:
        if m := re.match(r'\[@(.*?)](.*)', value):
            yield {'@language': m[1], '@value': m[2]}
        else:
            yield value


class RepositoryService:
    def __init__(self, endpoint: str, prefix: str):
        self.endpoint = endpoint
        self.prefix = prefix

    def get_resource_uri(self, iiif_id: str) -> str:
        """Converts a IIIF ID to a repository URI.

        ```pycon
        >>> repo_service = RepositoryService(endpoint='http://example.com/repo', prefix='fcrepo:')

        >>> repo_service.get_iiif_id('http://example.com/repo/foo/bar/123')
        'fcrepo:foo:bar:123'

        >>> repo_service.get_resource_uri('fcrepo:other:resource:5:678')
        'http://example.com/repo/other/resource/5/678'

        ```
        """
        if ':' not in iiif_id:
            logger.error(f'Invalid manifest id. Expecting "<prefix>:<local part>", got "{iiif_id}"')
            raise IdentifierError(iiif_id)
        prefix, local_part = iiif_id.split(':', 1)
        if prefix != self.prefix.rstrip(':'):
            logger.error(f'Unknown prefix "{prefix}:", expecting "{self.prefix}"')
            raise IdentifierError(iiif_id)

        repo_path = '/' + local_part.replace(':', '/')
        return self.endpoint + repo_path

    def get_iiif_id(self, resource_uri: str) -> str:
        if not resource_uri.startswith(self.endpoint):
            logger.error(f'{resource_uri} not part of configured repository {self.endpoint}')
            raise URLError(resource_uri)
        return resource_uri.replace(f'{self.endpoint}/', f'{self.prefix}').replace('/', ':')


class IdentifierError(ValueError):
    pass


class URLError(ValueError):
    pass


class PreservationFileError(Exception):
    pass


class Resource:
    """A digital object that has a IIIF manifest."""

    def __init__(self, doc: dict, metadata_queries: Mapping[str, str] = None):
        self.doc = doc
        self.metadata_queries = metadata_queries or {}
        self._pages = {page_doc['id']: page_doc for page_doc in self.doc['object__has_member']}
        self._files = {}
        for page_doc in self._pages.values():
            self._files.update({file_doc['id']: file_doc for file_doc in page_doc.get('page__has_file', [])})

    @property
    def uri(self) -> str:
        return self.doc['id']

    @property
    def title(self) -> list[str]:
        return self.get_metadata_values('Title')

    @property
    def page_uris(self) -> list[str]:
        return self.doc.get('page_uri_sequence__uris', [])

    @property
    def date(self) -> str:
        return self.get_metadata_values('Date')[0]

    @property
    def license(self) -> str:
        return self.doc.get('object__rights__same_as__uris')[0]

    @property
    def metadata(self) -> list[dict]:
        metadata = [{'label': k, 'value': self.get_metadata_values(k)} for k in self.metadata_queries.keys()]
        return [m for m in metadata if m['value']]

    def get_metadata_values(self, key: str):
        query = self.metadata_queries[key]
        return list(format_language_tags(jq.all(query, self.doc)))

    def get_page_doc(self, page_uri: str):
        return self._pages[page_uri]

    def find_page_doc(self, file_uri: str) -> dict:
        return self._pages[self._files[file_uri]['file__file_of__uri']]

    def get_page_index(self, page_uri: str) -> int:
        return self.page_uris.index(page_uri)

    def get_page_image_id(self, page_uri: str) -> str:
        return self.doc['iiif_thumbnail_sequence__ids'][self.get_page_index(page_uri)]

    def get_page_title(self, page_uri: str):
        return self._pages[page_uri].get('page__title__txt')


class SolrLookupError(Exception):
    pass


class SolrDocumentNotFound(SolrLookupError):
    pass


class SolrService:
    def __init__(self, endpoint: str, metadata_queries: Mapping[str, str]):
        self.endpoint = endpoint
        self.solr = pysolr.Solr(self.endpoint)
        self.metadata_queries = metadata_queries

    def get_doc(self, resource_uri: str) -> dict:
        try:
            # use the term query parser and pass the URI as a regular query parameter
            # so that Solr itself will handle the escaping of the URI value
            results = self.solr.search(q='{!term f=id v=$id}', id=resource_uri)
        except pysolr.SolrError as e:
            raise SolrLookupError(str(e)) from e

        if len(results) == 0:
            raise SolrDocumentNotFound(f'No document with id "{resource_uri}" found')
        if len(results) > 1:
            raise SolrLookupError(f'Multiple documents with id "{resource_uri}" found')

        return results.docs[0]

    def get_resource(self, resource_uri: str) -> Resource:
        return Resource(self.get_doc(resource_uri), self.metadata_queries)

    def get_text_matches(self, resource_uri: str, text_query: str, index: int = None):
        text_match_field = 'extracted_text__dps_txt'
        # use a unique match tag to mark the parts of the snippets
        # we want to extract into annotations
        match_tag = f'<<{uuid4()}>>'
        try:
            results = self.solr.search(
                q='{!term f=id v=$id}',
                id=resource_uri,
                hl='on',
                **{
                    'hl.fl': text_match_field,
                    'hl.q': f'{text_match_field}:{text_query}',
                    'hl.snippets': 100,
                    'hl.fragsize': 50,
                    'hl.maxAnalyzedChars': 1_000_000,
                    'hl.tag.pre': match_tag,
                    'hl.tag.post': match_tag,
                },
            )
        except pysolr.SolrError as e:
            raise SolrLookupError(str(e)) from e

        hits = []
        for text in results.highlighting[resource_uri].get(text_match_field, []):
            hits.extend(TaggedText.parse(x) for i, x in enumerate(text.split(match_tag)) if i % 2 == 1)

        if index is not None:
            return [h for h in hits if int(h.params['n']) == index]
        else:
            return hits


class TaggedText(NamedTuple):
    text: str
    params: dict

    @classmethod
    def parse(cls, dps_string: str):
        text, tag = dps_string.split('|', 1)
        return cls(
            text=text,
            params=dict(parse_qsl(tag)),
        )
