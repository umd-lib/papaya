from functools import cached_property
from typing import Any
from urllib.parse import urlencode

from papaya.iiif.presentation import Manifest, Canvas
from papaya.iiif import PRESENTATION_API_2_CONTEXT
from papaya.source import SolrHit


class SearchResultsList:
    """IIIF Annotation List of full text search results"""

    def __init__(self, target: Manifest | Canvas, query: str):
        self.target = target
        if isinstance(self.target, Manifest):
            self.manifest = self.target
            self.canvas = None
        elif isinstance(self.target, Canvas):
            self.canvas = self.target
            self.manifest = self.canvas.manifest
        self.query = query

    @property
    def uri(self) -> str:
        query_string = urlencode({'q': self.query})
        return f'{self.target.uri}/search?{query_string}'

    @cached_property
    def search_hits(self) -> list[SolrHit]:
        return self.target.search_text(self.query)

    @cached_property
    def result_annotations(self) -> list[SearchResult]:
        return [SearchResult(self, hit) for hit in self.search_hits]

    @cached_property
    def context_annotations(self) -> list[SearchResultContext]:
        return [SearchResultContext(result) for result in self.result_annotations]

    def json(self, with_context: bool = False) -> dict[str, Any]:
        list_info = {
            '@id': self.uri,
            '@type': 'sc:AnnotationList',
            'resources': [annotation.json() for annotation in self.result_annotations],
            'hits': [annotation.json() for annotation in self.context_annotations],
        }

        if with_context:
            list_info.update({'@context': PRESENTATION_API_2_CONTEXT})

        return list_info


class SearchResult:
    """IIIF Annotation of a single search result"""

    def __init__(self, results: SearchResultsList, hit: SolrHit):
        self.results = results
        self.hit = hit

    @property
    def uri(self) -> str:
        return f'{self.results.uri}#result-{self.hit.id}'

    @property
    def canvas(self) -> Canvas:
        return self.results.manifest.find_canvas(self.hit.match.params['n'])

    def json(self) -> dict[str, Any]:
        return {
            '@id': self.uri,
            '@type': 'oa:Annotation',
            'motivation': 'sc:painting',
            'resource': {
                '@type': 'cnt:ContentAsText',
                'format': 'text/plain',
                'chars': self.hit.match.text,
            },
            'on': f'{self.canvas.uri}#xywh={self.hit.match.params["xywh"]}',
        }


class SearchResultContext:
    """Context (i.e., preceding and following text) for a single `SearchResult`"""

    def __init__(self, result: SearchResult):
        self.result = result

    def json(self) -> dict[str, Any]:
        return {
            '@type': 'search:Hit',
            'annotations': [self.result.uri],
            'before': self.result.hit.before,
            'match': self.result.hit.match.text,
            'after': self.result.hit.after,
        }
