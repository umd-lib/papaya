from fractions import Fraction
from typing import NamedTuple, Any

import requests

from papaya.source import Resource

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


class ImageService:
    def __init__(self, endpoint: str, thumbnail_width: int = 250):
        self.endpoint = endpoint
        self.thumbnail_width = thumbnail_width

    def get_metadata(self, image_id: str) -> ImageInfo:
        url = f'{self.endpoint}/{image_id}'
        response = requests.get(url)
        if not response.ok:
            raise RuntimeError('Problem retrieving image')
        info = response.json()
        return ImageInfo(
            uri=info['@id'],
            context=info['@context'],
            profile=info['profile'],
            width=info['width'],
            height=info['height']
        )


FULL_IMAGE_PARAMS = ImageParams('full', 'full', '0', 'default', 'jpg')


class Manifest:
    def __init__(self, base_uri: str, resource: Resource, image_service: ImageService, logo_url: str = None):
        self.base_uri = base_uri
        self.resource = resource
        self.image_service = image_service
        self.logo_url = logo_url
        self._sequences = None

    @property
    def uri(self):
        return f'{self.base_uri}/manifest'

    @property
    def sequences(self) -> list[Sequence]:
        if self._sequences is None:
            self._sequences = [Sequence(manifest=self, name='normal')]
        return self._sequences

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

        if self.logo_url is not None:
            manifest_info['logo'] = {'@id': self.logo_url}

        if with_context:
            manifest_info.update({'@context': PRESENTATION_API_CONTEXT})

        return manifest_info


class Sequence:
    def __init__(self, manifest: Manifest, name: str):
        self.manifest = manifest
        self.name = name
        self.resource = self.manifest.resource
        self._canvases = None

    @property
    def uri(self) -> str:
        return f'{self.manifest.base_uri}/sequence/{self.name}'

    @property
    def canvases(self) -> list[Canvas]:
        if self._canvases is None:
            self._canvases = [
                Canvas(sequence=self, name=f'{index:04d}', page_uri=page_uri)
                for index, page_uri in enumerate(self.resource.page_uris, 1)
            ]
        return self._canvases

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
        self._image_annotation = None
        self._thumbnail = None

    @property
    def uri(self) -> str:
        return f'{self.manifest.base_uri}/canvas/{self.name}'

    @property
    def image_annotation(self) -> Annotation:
        if self._image_annotation is None:
            self._image_annotation = Annotation(
                canvas=self,
                name=f'{self.name}-image',
                motivation='sc:painting',
                resource=Image(
                    service=self.manifest.image_service,
                    image_id=self.image_id,
                    iiif_params=FULL_IMAGE_PARAMS,
                ),
            )
        return self._image_annotation

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
        return f'{self.manifest.base_uri}/annotation/{self.name}'

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
        self._info = None

    @property
    def uri(self) -> str:
        if self.iiif_params is not None:
            return self.info.uri + str(self.iiif_params)
        else:
            return self.info.uri

    @property
    def info(self) -> ImageInfo:
        if self._info is None:
            self._info = self.service.get_metadata(self.image_id)
        return self._info

    def thumbnail_dict(self) -> dict[str, Any]:
        width = self.service.thumbnail_width
        height = int(width / self.info.aspect_ratio)
        thumbnail_params = ImageParams(size=f'{width},{height}')
        image = self.to_dict()
        image.update({
            '@id': self.info.uri + str(thumbnail_params),
            'height': height,
            'width': width,
        })
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
