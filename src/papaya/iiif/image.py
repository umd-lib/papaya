import logging
from dataclasses import dataclass
from fractions import Fraction
from typing import NamedTuple

import requests
from urlobject import URLObject

logger = logging.getLogger(__name__)


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

    @property
    def mime_type(self) -> str:
        match self.format:
            case 'jpg':
                return 'image/jpeg'
            case 'tif':
                return 'image/tiff'
            case 'png':
                return 'image/png'
            case 'gif':
                return 'image/gif'
            case 'jp2':
                return 'image/jp2'
            case 'pdf':
                return 'application/pdf'
            case 'webp':
                return 'image/webp'
            case _:
                return 'application/octet-stream'


class ImageInfo(NamedTuple):
    """Image information from the IIIF Image API service"""

    uri: str
    """Image URI"""
    context: str | dict
    """JSON-LD context"""
    profile: str | dict
    """IIIF Image API profile"""
    width: int
    """Image width"""
    height: int
    """Image height"""

    @property
    def aspect_ratio(self) -> Fraction:
        """Image aspect ratio (`width / height`)"""
        return Fraction(self.width, self.height)


class ImageServiceError(Exception):
    """There was a problem communicating with the IIIF Image API server"""


@dataclass
class ImageResource:
    endpoint: URLObject
    image_id: str
    origin: URLObject | None = None

    def request_url(self, params: ImageParams = None) -> str:
        base = self.origin if self.origin else self.endpoint
        if params is not None:
            return f'{base}/{self.image_id}{params}'
        else:
            return f'{base}/{self.image_id}'

    @property
    def info_url(self):
        return f'{self.request_url()}/info.json'

    def uri(self, params: ImageParams = None) -> str:
        if params is not None:
            return f'{self.endpoint}/{self.image_id}{params}'
        else:
            return f'{self.endpoint}/{self.image_id}'

    @property
    def forwarding_headers(self) -> dict[str, str]:
        if self.origin is None:
            return {}

        forwarding_headers = {
            'X-Forwarded-Proto': self.endpoint.scheme,
            'X-Forwarded-Host': self.endpoint.hostname,
        }
        if self.endpoint.path != self.origin.path:
            forwarding_headers['X-Forwarded-Path'] = str(self.endpoint.path).removesuffix(self.origin.path)

        return forwarding_headers


class ImageService:
    """IIIF Image API service endpoint."""

    def __init__(self, endpoint: str, origin: str = None, thumbnail_width: int = 250):
        self.endpoint = URLObject(endpoint)
        self.origin = URLObject(origin) if origin is not None else None
        self.thumbnail_width = thumbnail_width

    def resource(self, image_id: str) -> ImageResource:
        return ImageResource(endpoint=self.endpoint, origin=self.origin, image_id=image_id)

    def get_metadata(self, image_id: str) -> ImageInfo:
        image_resource = self.resource(image_id)
        try:
            response = requests.get(image_resource.info_url, headers=image_resource.forwarding_headers)
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
