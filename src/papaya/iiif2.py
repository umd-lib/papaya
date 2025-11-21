import logging
from dataclasses import dataclass
from fractions import Fraction
from functools import cached_property
from typing import NamedTuple, Any
from urllib.parse import urlencode

import requests

from papaya.errors import IdentifierProblem, ManifestNotFound, ServiceProblem, ManifestNotAvailable
from papaya.source import (
    Resource,
    SolrService,
    RepositoryService,
    IdentifierError,
    URLError,
    SolrDocumentNotFound,
    SolrLookupError,
    TaggedText,
)

logger = logging.getLogger(__name__)

PRESENTATION_API_CONTEXT = 'http://iiif.io/api/presentation/2/context.json'
DEFAULT_THUMBNAIL_WIDTH = 250


class ImageParams(NamedTuple):
    """Tuple for holding a set of IIIF Image API parameters. See
    https://iiif.io/api/image/2.0/#image-request-parameters for information
    about each parameter."""

    region: str = 'full'
    """`full` | `{x},{y},{w},{h}` | `pct:{x},{y},{w},{h}`"""
    size: str = 'full'
    """`full` | `{w},` | `,{h}` | `pct:{n}` | `{w},{h}` | `!{w},{h}`"""
    rotation: str = '0'
    """`{n}` | `!{n}`"""
    quality: str = 'default'
    """`color` | `gray` | `bitonal` | `default`"""
    format: str = 'jpg'
    """`jpg` | `tif` | `png` | `gif` | `jp2` | `pdf` | `webp`"""

    def __str__(self):
        return f'/{self.region}/{self.size}/{self.rotation}/{self.quality}.{self.format}'


class ImageInfo(NamedTuple):
    uri: str
    context: str | dict
    profile: str | dict
    width: int
    height: int

    @property
    def aspect_ratio(self) -> Fraction:
        return Fraction(self.width, self.height)


class ImageServiceError(Exception):
    pass


class ImageService:
    def __init__(self, endpoint: str, thumbnail_width: int = 250):
        self.endpoint = endpoint
        self.thumbnail_width = thumbnail_width

    def get_metadata(self, image_id: str) -> ImageInfo:
        url = f'{self.endpoint}/{image_id}'
        try:
            response = requests.get(url)
        except requests.ConnectionError as e:
            logger.error(f'Unable to retrieve metadata from IIIF Image Service: {e}')
            raise ImageServiceError(f'Problem retrieving image: {e}') from e
        if not response.ok:
            raise ImageServiceError(f'Problem retrieving image: {response.status_code}')
        info = response.json()
        return ImageInfo(
            uri=info['@id'],
            context=info['@context'],
            profile=info['profile'],
            width=info['width'],
            height=info['height'],
        )


FULL_IMAGE_PARAMS = ImageParams('full', 'full', '0', 'default', 'jpg')


class Manifest:
    def __init__(self, ctx: PresentationContext, id: str, text_query: str = None):
        self.ctx = ctx
        self.id = id
        self.text_query = text_query

    @property
    def base_uri(self) -> str:
        return self.ctx.endpoint_url

    @property
    def uri(self) -> str:
        return f'{self.base_uri}/{self.id}/manifest'

    @cached_property
    def resource(self) -> Resource:
        return self.ctx.get_resource(self.id)

    @cached_property
    def sequences(self) -> list[Sequence]:
        return [Sequence(manifest=self, name='normal')]

    def find_sequence(self, name: str) -> Sequence:
        for sequence in self.sequences:
            if sequence.name == name:
                return sequence
        else:
            raise KeyError(name)

    def find_canvas(self, name: str) -> Canvas:
        for sequence in self.sequences:
            for canvas in sequence.canvases:
                if canvas.name == name:
                    return canvas
        else:
            raise KeyError(name)

    def find_annotation(self, name: str) -> Annotation:
        for sequence in self.sequences:
            for canvas in sequence.canvases:
                if canvas.image_annotation.name == name:
                    return canvas.image_annotation
        else:
            raise KeyError(name)

    def to_dict(self, with_context: bool = False) -> dict[str, Any]:
        manifest_info: dict[str, Any] = {
            '@id': self.uri,
            '@type': 'sc:Manifest',
            'label': self.resource.title[0],
            'metadata': self.resource.metadata,
            'sequences': [seq.to_dict() for seq in self.sequences],
            'navDate': self.resource.date,
            'license': self.resource.license,
        }
        try:
            manifest_info['thumbnail'] = self.sequences[0].canvases[0].image_annotation.thumbnail_dict()
        except IndexError:
            pass

        if self.ctx.logo_url is not None:
            manifest_info['logo'] = {'@id': self.ctx.logo_url}

        if with_context:
            manifest_info.update({'@context': PRESENTATION_API_CONTEXT})

        return manifest_info


class Sequence:
    def __init__(self, manifest: Manifest, name: str):
        self.manifest = manifest
        self.ctx = self.manifest.ctx
        self.name = name
        self.resource = self.manifest.resource

    @property
    def uri(self) -> str:
        return f'{self.manifest.base_uri}/{self.manifest.id}/sequence/{self.name}'

    @cached_property
    def canvases(self) -> list[Canvas]:
        return [
            Canvas(sequence=self, name=str(index), page_uri=page_uri)
            for index, page_uri in enumerate(self.resource.page_uris)
        ]

    def get_canvas(self, name: str) -> Canvas:
        for canvas in self.canvases:
            if canvas.name == name:
                return canvas
        else:
            raise KeyError(name)

    def to_dict(self, with_context: bool = False) -> dict[str, Any]:
        sequence_info = {
            '@id': self.uri,
            '@type': 'sc:Sequence',
            'canvases': [canvas.to_dict() for canvas in self.canvases],
        }
        if len(self.canvases) > 0:
            sequence_info['startCanvas'] = self.canvases[0].uri

        if with_context:
            sequence_info.update({'@context': PRESENTATION_API_CONTEXT})

        return sequence_info


class Canvas:
    def __init__(self, sequence: Sequence, name: str, page_uri: str):
        self.sequence = sequence
        self.name = name
        self.page_uri = page_uri
        self.manifest = self.sequence.manifest
        self.resource = self.manifest.resource
        self.image_id = self.resource.get_page_image_id(self.page_uri)

    @property
    def uri(self) -> str:
        return f'{self.manifest.base_uri}/{self.manifest.id}/canvas/{self.name}'

    @cached_property
    def image_annotation(self) -> Annotation:
        return Annotation(
            canvas=self,
            name=f'{self.name}-image',
            motivation='sc:painting',
            resource=Image(
                service=self.manifest.ctx.image_service,
                image_id=self.image_id,
                iiif_params=FULL_IMAGE_PARAMS,
            ),
        )

    def search_text(self, query: str) -> list[TaggedText]:
        resource_uri = self.manifest.resource.uri
        page_index = int(self.name)
        return self.manifest.ctx.solr_service.get_text_matches(resource_uri, query, page_index)

    def to_dict(self, with_context: bool = False) -> dict[str, Any]:
        canvas_info = {
            '@id': self.uri,
            '@type': 'sc:Canvas',
            'label': self.resource.get_page_title(self.page_uri),
            'images': [self.image_annotation.to_dict()],
            'thumbnail': self.image_annotation.thumbnail_dict(),
            'height': self.image_annotation.height,
            'width': self.image_annotation.width,
            'otherContent': [],
        }

        if self.manifest.text_query is not None:
            canvas_info['otherContent'].append(
                {
                    '@id': SearchHitsList(self, self.manifest.text_query).uri,
                    '@type': 'sc:AnnotationList',
                }
            )

        if with_context:
            canvas_info.update({'@context': PRESENTATION_API_CONTEXT})

        return canvas_info


class Annotation:
    def __init__(self, canvas: Canvas, name: str, motivation: str, resource: Image):
        self.canvas = canvas
        self.manifest = self.canvas.manifest
        self.name = name
        self.motivation = motivation
        self.resource = resource

    @property
    def uri(self) -> str:
        return f'{self.manifest.base_uri}/{self.manifest.id}/annotation/{self.name}'

    @property
    def width(self) -> int:
        return self.resource.info.width

    @property
    def height(self) -> int:
        return self.resource.info.height

    def thumbnail_dict(self) -> dict[str, Any]:
        return self.resource.thumbnail_dict()

    def to_dict(self, with_context: bool = False) -> dict[str, Any]:
        annotation_info = {
            '@id': self.uri,
            '@type': 'oa:Annotation',
            'motivation': self.motivation,
            'resource': self.resource.to_dict(),
            'on': self.canvas.uri,
        }

        if with_context:
            annotation_info.update({'@context': PRESENTATION_API_CONTEXT})

        return annotation_info


class Image:
    def __init__(self, service: ImageService, image_id: str, iiif_params: ImageParams = None):
        self.service = service
        self.image_id = image_id
        self.iiif_params = iiif_params

    @property
    def uri(self) -> str:
        if self.iiif_params is not None:
            return self.info.uri + str(self.iiif_params)
        else:
            return self.info.uri

    @cached_property
    def info(self) -> ImageInfo:
        return self.service.get_metadata(self.image_id)

    def thumbnail_dict(self) -> dict[str, Any]:
        width = self.service.thumbnail_width
        height = int(width / self.info.aspect_ratio)
        thumbnail_params = ImageParams(size=f'{width},{height}')
        image = self.to_dict()
        image.update(
            {
                '@id': self.info.uri + str(thumbnail_params),
                'height': height,
                'width': width,
            }
        )
        return image

    def to_dict(self) -> dict[str, Any]:
        return {
            '@id': self.uri,
            '@type': 'dctypes:Image',
            'service': {
                '@context': self.info.context,
                '@id': self.info.uri,
                'profile': self.info.profile,
            },
            'format': 'image/jpeg',
            'height': self.info.height,
            'width': self.info.width,
        }


class SearchHitsList:
    def __init__(self, canvas: Canvas, query: str):
        self.canvas = canvas
        self.manifest = self.canvas.manifest
        self.query = query

    @property
    def uri(self) -> str:
        query_string = urlencode({'q': self.query})
        return f'{self.manifest.base_uri}/{self.manifest.id}/list/{self.canvas.name}-search?{query_string}'

    @cached_property
    def search_hits(self):
        return self.canvas.search_text(self.query)

    @cached_property
    def annotations(self):
        return [hit_annotation(f'#result-{i:03d}', self.canvas.uri, hit) for i, hit in enumerate(self.search_hits, 1)]

    def to_dict(self, with_context: bool = False) -> dict[str, Any]:
        list_info = {'@id': self.uri, '@type': 'sc:AnnotationList', 'resources': self.annotations}

        if with_context:
            list_info.update({'@context': PRESENTATION_API_CONTEXT})

        return list_info


def hit_annotation(uri, canvas_uri, hit: TaggedText):
    return {
        '@id': uri,
        '@type': [
            'oa:Annotation',
            'umd:searchResult',
        ],
        'motivation': 'oa:highlighting',
        'on': {
            '@type': 'oa:SpecificResource',
            'full': canvas_uri,
            'selector': {
                '@type': 'oa:FragmentSelector',
                'value': f'xywh={hit.params["xywh"]}',
            },
        },
    }


@dataclass
class PresentationContext:
    solr_service: SolrService
    repo_service: RepositoryService
    image_service: ImageService
    endpoint_url: str
    logo_url: str

    def get_resource_uri(self, iiif_id: str) -> str:
        try:
            return self.repo_service.get_resource_uri(iiif_id)
        except IdentifierError as e:
            raise IdentifierProblem(iiif_id=str(e)) from e

    def get_iiif_id(self, resource_uri: str) -> str:
        try:
            return self.repo_service.get_iiif_id(resource_uri)
        except URLError as e:
            raise ManifestNotAvailable(uri=resource_uri) from e

    def get_resource(self, manifest_id: str):
        try:
            return self.solr_service.get_resource(self.get_resource_uri(manifest_id))
        except SolrDocumentNotFound as e:
            raise ManifestNotFound(id=manifest_id) from e
        except SolrLookupError as e:
            raise ServiceProblem from e

    def get_manifest(self, manifest_id: str, text_query: str = None):
        return Manifest(ctx=self, id=manifest_id, text_query=text_query)
