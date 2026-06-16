from functools import cached_property
from typing import Any

from papaya.iiif import PRESENTATION_API_2_CONTEXT, SEARCH_API_1_CONTEXT, SEARCH_API_1_PROFILE
from papaya.iiif.image import ImageParams, ImageInfo, ImageService, FULL_IMAGE_PARAMS
from papaya.source import Resource, SolrHit


class Manifest:
    """IIIF Manifest"""

    def __init__(self, ctx, id: str):
        self.ctx = ctx
        self.id: str = id

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

    def find_annotation(self, name: str) -> ImageAnnotation:
        for sequence in self.sequences:
            for canvas in sequence.canvases:
                if canvas.image_annotation.name == name:
                    return canvas.image_annotation
        else:
            raise KeyError(name)

    def search_text(self, query: str) -> list[SolrHit]:
        resource_uri = self.resource.uri
        return self.ctx.solr_service.get_text_matches(resource_uri, query)

    def json(self, with_context: bool = False) -> dict[str, Any]:
        manifest_info: dict[str, Any] = {
            '@id': self.uri,
            '@type': 'sc:Manifest',
            'label': self.resource.label,
            'metadata': self.resource.metadata,
            'description': self.resource.description,
            'sequences': [seq.json() for seq in self.sequences],
            'service': [],
            'navDate': self.resource.date,
            'license': self.resource.license,
        }
        if self.resource.is_searchable:
            manifest_info['service'].append({
                '@context': SEARCH_API_1_CONTEXT,
                '@id': f'{self.uri}/search',
                'profile': SEARCH_API_1_PROFILE,
            })
        try:
            manifest_info['thumbnail'] = self.sequences[0].canvases[0].thumbnail.json()
        except IndexError:
            pass

        if self.ctx.logo_url is not None:
            manifest_info['logo'] = {'@id': self.ctx.logo_url}

        if with_context:
            manifest_info.update({'@context': PRESENTATION_API_2_CONTEXT})

        return manifest_info


class Sequence:
    """IIIF Sequence"""

    def __init__(self, manifest: Manifest, name: str):
        self.manifest: Manifest = manifest
        self.name: str = name
        self.ctx = self.manifest.ctx
        self.resource: Resource = self.manifest.resource

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

    def json(self, with_context: bool = False) -> dict[str, Any]:
        sequence_info = {
            '@id': self.uri,
            '@type': 'sc:Sequence',
            'canvases': [canvas.json() for canvas in self.canvases],
        }

        if with_context:
            sequence_info.update({'@context': PRESENTATION_API_2_CONTEXT})

        return sequence_info


class Canvas:
    """IIIF Canvas"""

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
    def image_annotation(self) -> ImageAnnotation:
        return ImageAnnotation(
            canvas=self,
            name=f'{self.name}-image',
            image=Image(
                service=self.manifest.ctx.image_service,
                image_id=self.image_id,
                iiif_params=FULL_IMAGE_PARAMS,
            ),
        )

    @cached_property
    def thumbnail(self) -> ThumbnailImage:
        return ThumbnailImage(self.manifest.ctx.image_service, self.image_id)

    def search_text(self, query: str) -> list[SolrHit]:
        resource_uri = self.manifest.resource.uri
        page_index = int(self.name)
        return self.manifest.ctx.solr_service.get_text_matches(resource_uri, query, page_index)

    def json(self, with_context: bool = False) -> dict[str, Any]:
        canvas_info = {
            '@id': self.uri,
            '@type': 'sc:Canvas',
            'label': self.resource.get_page_label(self.page_uri),
            'images': [self.image_annotation.json()],
            'thumbnail': self.thumbnail.json(),
            'height': self.image_annotation.height,
            'width': self.image_annotation.width,
            'otherContent': [],
        }

        if with_context:
            canvas_info.update({'@context': PRESENTATION_API_2_CONTEXT})

        return canvas_info


class ImageAnnotation:
    """IIIF Image Annotation"""

    def __init__(self, canvas: Canvas, name: str, image: Image, motivation: str = 'sc:painting'):
        self.canvas = canvas
        self.manifest = self.canvas.manifest
        self.name = name
        self.motivation = motivation
        self.image = image

    @property
    def uri(self) -> str:
        return f'{self.manifest.base_uri}/{self.manifest.id}/annotation/{self.name}'

    @property
    def width(self) -> int:
        return self.image.info.width

    @property
    def height(self) -> int:
        return self.image.info.height

    def json(self, with_context: bool = False) -> dict[str, Any]:
        annotation_info = {
            '@id': self.uri,
            '@type': 'oa:Annotation',
            'motivation': self.motivation,
            'resource': self.image.json(),
            'on': self.canvas.uri,
        }

        if with_context:
            annotation_info.update({'@context': PRESENTATION_API_2_CONTEXT})

        return annotation_info


class Image:
    """IIIF Image"""

    def __init__(self, service: ImageService, image_id: str, iiif_params: ImageParams | None = None):
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

    def json(self) -> dict[str, Any]:
        image_info = {
            '@id': self.uri,
            '@type': 'dctypes:Image',
            'service': {
                '@context': self.info.context,
                '@id': self.info.uri,
                'profile': self.info.profile,
            },
            'height': self.info.height,
            'width': self.info.width,
        }

        if self.iiif_params is not None:
            image_info['format'] = self.iiif_params.format

        return image_info


class ThumbnailImage(Image):
    """IIIF thumbnail image"""

    def __init__(self, service: ImageService, image_id: str):
        super().__init__(service, image_id)
        self.width = self.service.thumbnail_width
        self.height = int(self.width / self.info.aspect_ratio)
        self.iiif_params = ImageParams(size=f'{self.width},{self.height}')

    def json(self) -> dict[str, Any]:
        image = super().json()
        image['width'] = self.width
        image['height'] = self.height
        return image
