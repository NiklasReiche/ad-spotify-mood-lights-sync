import numbers
from enum import Enum

import appdaemon.plugins.hass.hassapi as hass
import math
import colorsys
from functools import partial

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from requests.exceptions import ConnectionError

from typing import Tuple, List, TypeVar, Callable, Iterable

RGB_Color = Tuple[int, int, int]
HS_Color = Tuple[int, int]
Point = Tuple[float, float]
T = TypeVar('T')
Num = TypeVar('Num', int, float)

DEFAULT_PROFILE = [
    ((0.0, 0.5), (128, 0, 128), 1.0),   # disgust - purple
    ((0.0, 1.0), (255, 0, 0), 1.0),     # angry - red
    ((0.5, 1.0), (255, 165, 0), 1.0),   # alert - orange
    ((1.0, 1.0), (255, 255, 0), 1.0),   # happy - yellow
    ((1.0, 0.0), (0, 205, 0), 1.0),     # calm - green
    ((0.5, 0.0), (0, 180, 255), 1.0),   # relaxed - bluegreen
    ((0.0, 0.0), (0, 0, 255), 1.0),     # sad - blue
]


class ColorMode(Enum):
    RGB = 'RGB'
    HS = 'HS'


class ColorProfile:
    def color_for_point(self, point: Point) -> RGB_Color:
        """Computes an RGB color value for a point on the color plane.

        :param point: coordinates in the range [0,1]X[0,1]

        :return: interpolated RGB color for the input point as [r, g, b] where 0 <= r,g,b <= 255
        """
        pass


class RGBColorProfile(ColorProfile):
    def __init__(self, data, global_weight=2.0):
        self.global_weight = global_weight
        self.points: List[Point] = [x[0] for x in data]
        self.local_weights: List[float] = [x[2] for x in data]
        self.channels: Tuple[List[int], List[int], List[int]] | Tuple[List[int], List[int]] = \
            ([x[1][0] for x in data],
             [x[1][1] for x in data],
             [x[1][2] for x in data])

    def color_for_point(self, point: Point) -> RGB_Color:
        weights = inverse_distance_weights(point, self.points, self.local_weights,
                                           global_weight=self.global_weight)

        # compute new RGB value as inverse distance weighted sum:
        red = interpolate(self.channels[0], weights)
        green = interpolate(self.channels[1], weights)
        blue = interpolate(self.channels[2], weights)

        # brightness should be max to not conflict with the light's brightness setting (equivalent to HS space)
        return to_max_brightness((int(red), int(green), int(blue)))


class HSColorProfile(ColorProfile):
    def __init__(self, mirror_x, mirror_y, rotate):
        self.mirror_x = mirror_x
        self.mirror_y = mirror_y
        self.rotate = rotate
        pass

    def color_for_point(self, point: Point) -> RGB_Color:
        point = (normalize(point[0], 0.0, 1.0, -1.0, 1.0),
                 normalize(point[1], 0.0, 1.0, -1.0, 1.0))
        # calculate hue from angle to center
        x = point[0] * (-1.0 if self.mirror_x else 1.0)
        y = point[1] * (-1.0 if self.mirror_y else 1.0)
        angle = math.degrees(math.atan2(y, x)) + self.rotate
        # map to 0-360 degree range
        hue = (angle + 360) % 360

        # calculate saturation as distance to center, clamped to unit circle
        distance = min(math.dist([0.0, 0.0], point), 1.0)  # TODO: drop-off
        saturation = normalize(distance, 0, 1, 0, 100)

        return hs_to_rgb((int(hue), int(100)))


def normalize(v, in_min, in_max, out_min, out_max):
    return (out_max - out_min) / (in_max - in_min) * (v - in_min) + out_min


def mul_array(list_a: Iterable[Num], list_b: Iterable[float]) -> List[float]:
    return [ab[0] * ab[1] for ab in zip(list_a, list_b)]


def mul_scalar(list_a: Iterable[Num], scalar: float) -> List[Num]:
    return [x * scalar for x in list_a]


def inverse_distance_weights(point: Point, points: List[Point], local_weights: List[float], global_weight=1.0):
    distances = [math.dist(point, p) for p in points]
    weights = [1 / ((d + 1E-6) ** (global_weight * w)) for d, w in zip(distances, local_weights)]
    return weights


def interpolate(values: List[Num], weights: List[float]):
    return sum(mul_array(values, weights)) / sum(weights)


def rgb_to_hs(color: RGB_Color) -> HS_Color:
    color = colorsys.rgb_to_hsv(
        normalize(color[0], 0, 255, 0, 1),
        normalize(color[1], 0, 255, 0, 1),
        normalize(color[2], 0, 255, 0, 1))

    return int(normalize(color[0], 0, 1, 0, 360)), \
        int(normalize(color[1], 0, 1, 0, 100))


def hs_to_rgb(color: HS_Color) -> RGB_Color:
    color = colorsys.hsv_to_rgb(
        normalize(color[0], 0, 360, 0, 1),
        normalize(color[1], 0, 100, 0, 1),
        1.0)

    return int(normalize(color[0], 0, 1, 0, 255)), \
        int(normalize(color[1], 0, 1, 0, 255)), \
        int(normalize(color[2], 0, 1, 0, 255))


def to_max_brightness(color: RGB_Color):
    return hs_to_rgb(rgb_to_hs(color))


class SpotifyMoodLightsSync(hass.Hass):
    """SpotifyMoodLightsSync class."""

    def initialize(self) -> None:
        """Initialize the app and listen for media_player media_content_id changes."""

        # setup light
        self.light = self.args.get('light')
        if not self.light:
            self.error("'light' not specified in app config", level='WARNING')

        # setup spotify component
        client_id = self.args.get('client_id')
        if not client_id:
            self.error("Spotify 'client_id' not specified in app config. Aborting startup", level='ERROR')
            return

        client_secret = self.args.get('client_secret')
        if not client_secret:
            self.error("Spotify 'client_secret' not specified in app config. Aborting startup", level='ERROR')
            return

        client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        self.sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

        self.max_retries = self.args.get('max_retries', 1)

        # setup color profile
        color_profile_arg = self.args.get('color_profile', 'default')
        if color_profile_arg == 'default' or color_profile_arg == 'centered':
            self.color_profile = RGBColorProfile(DEFAULT_PROFILE)
        elif color_profile_arg == 'saturated':
            self.color_profile = HSColorProfile(True, False, -60)
        elif color_profile_arg == 'custom':
            custom_profile = self.args.get('custom_profile')
            if type(custom_profile) is list:  # legacy config, assume RGB values without weights
                self.error("Using deprecated custom_profile config format. See README for new format.", level='WARNING')
                try:
                    data = [(x['point'], x['color'], 1.0) for x in custom_profile]

                    assert len(data) > 0
                    assert all([len(p) == 2 and len(c) == 3 for p, c, w in data])
                    assert all([0 <= p[0] <= 1 and 0 <= p[1] <= 1 for p, c, w in data])
                    assert all([0 <= c[0] <= 255 and 0 <= c[1] <= 255 and 0 <= c[2] <= 255 for p, c, w in data])

                    self.color_profile = RGBColorProfile(data, weight=1.0)

                except (KeyError, AssertionError):
                    self.error("Profile set to 'custom' but 'custom_profile' is malformed. Falling back to the default "
                               "profile", level='WARNING')
                    self.color_profile = RGBColorProfile(DEFAULT_PROFILE)
            elif custom_profile:
                try:
                    mode = custom_profile['color_mode']
                    weight = custom_profile.get('global_weight', 1.5)
                    data = [(x['point'], x['color'], x.get('local_weight', 1.0))
                            for x in custom_profile['sample_data']]

                    assert len(data) > 0
                    assert all([isinstance(w, numbers.Number) for p, c, w in data])
                    assert all([0 <= p[0] <= 1 and 0 <= p[1] <= 1 for p, c, w in data])

                    if mode == 'rgb':
                        assert all([len(p) == 2 and len(c) == 3 for p, c, w in data])
                        assert all([0 <= c[0] <= 255 and 0 <= c[1] <= 255 and 0 <= c[2] <= 255 for p, c, w in data])

                        self.color_profile = RGBColorProfile(data, weight=weight)

                    elif mode == 'hs':
                        assert all([len(p) == 2 and len(c) == 2 for p, c, w in data])
                        assert all([0 <= c[0] <= 360 and 0 <= c[1] <= 100 for p, c, w in data])

                        self.color_profile = HSColorProfile(data, weight=weight)

                    else:
                        self.error(
                            f"Unknown color mode '{mode}' in 'custom_profile'. Must be 'rgb' or 'hs'. Falling back to "
                            f"the default profile", level='WARNING')
                        self.color_profile = RGBColorProfile(DEFAULT_PROFILE)
                except (KeyError, AssertionError):
                    self.error("Profile set to 'custom' but 'custom_profile' is malformed. Falling back to the default "
                               "profile", level='WARNING')
                    self.color_profile = RGBColorProfile(DEFAULT_PROFILE)
            else:
                self.error("Profile set to 'custom' but no 'custom_profile' specified in app config. Falling back to "
                           "the default profile", level='WARNING')
                self.color_profile = RGBColorProfile(DEFAULT_PROFILE)
        else:
            self.error(f"Unknown profile '{color_profile_arg}'. Falling back to the default profile", level='WARNING')
            self.color_profile = RGBColorProfile(DEFAULT_PROFILE)

        # output color map as image for debugging
        color_map_image = self.args.get("color_map_image")
        if color_map_image is not None:
            size = color_map_image.get('size')
            location = color_map_image.get('location')
            if size and location:
                from PIL import Image
                im = Image.new('RGB', (size, size))
                im.putdata(self.create_color_map_image(size, size))
                try:
                    im.save(location)
                except OSError as e:
                    self.error(f"Could not write image to path '{location}'. Reason: {e.strerror}", level='WARNING')
            else:
                self.error("'color_map_image' specified, but 'size' or 'location' not specified in app config. "
                           "Skipping image generation", level='WARNING')

        # register callback
        media_player = self.args.get('media_player')
        if not media_player:
            self.error("'media_player' not specified in app config. Aborting startup", level='ERROR')
            return

        if self.args.get('mode', 'direct') == 'direct':
            self.listen_state(self.sync_lights_from_spotify, media_player, attribute='media_content_id')
        elif self.args['mode'] == 'search':
            self.listen_state(self.sync_lights_from_search, media_player, attribute='all')

        self.log(f"App started. Listening on {media_player}")

    def sync_lights_from_spotify(self, entity: str, attribute: str, old_uri: str, new_uri: str, kwargs) -> None:
        if new_uri is None or old_uri == new_uri:
            return

        self.sync_light(new_uri)

    def sync_lights_from_search(self, entity: str, attribute: str, old: dict, new: dict, kwargs) -> None:
        title = new['attributes'].get('media_title')
        artist = new['attributes'].get('media_artist')
        old_title = old['attributes'].get('media_title')
        old_artist = new['attributes'].get('media_artist')

        if not title or not artist or old_title == title and old_artist == artist:
            return

        try:
            results = self.call_api(partial(self.sp.search, q=f'artist:{artist} track:{title}', type='track'))
        except ConnectionError as e:
            self.error(f"Could not reach Spotify API, skipping track. Reason: {e}", level='WARNING')
            return

        if len(results['tracks']['items']) == 0:
            self.log(f"Could not find track id for '{title}' by '{artist}'. Searching just by title...", level='INFO')

            try:
                results = self.call_api(partial(self.sp.search, q=f'track:{title}', type='track'))
            except ConnectionError as e:
                self.error(f"Could not reach Spotify API, skipping track. Reason: {e}", level='WARNING')
                return

            if len(results['tracks']['items']) == 0:
                self.error(f"Could not find track id for '{title}'. Skipping track.", level='WARNING')
                return

        track_uri = results['tracks']['items'][0]['uri']
        self.log(f"Found track id '{track_uri}' for '{title}' by '{artist}'", level='DEBUG')
        self.sync_light(track_uri)

    def sync_light(self, track_uri: str) -> None:
        try:
            color = self.color_from_uri(track_uri)
        except ConnectionError as e:
            self.error(f"Could not reach Spotify API, skipping track. Reason: {e}", level='WARNING')
            return
        except ValueError as e:
            self.error(f"Could not find features for track uri {track_uri}. This may be caused by trying to use a "
                       f"non-spotify media_player in 'direct' mode. Try using 'search' mode instead.\n"
                       f"Reason: {e}", level='ERROR')
            return

        # color is processed even if no light was specified, could be used for debugging
        if self.light is None:
            return

        # the color mode used here should not matter, since HA already converts it to a mode supported by the light
        self.turn_on(self.light, **{'rgb_color': color})

    def color_from_uri(self, track_uri: str) -> RGB_Color:
        """Get the color from a spotify track uri."""

        track_features = self.call_api(partial(self.sp.audio_features, track_uri))[0]
        if not track_features:
            raise ValueError("no track features found for uri")

        valence: float = track_features['valence']
        energy: float = track_features['energy']
        color = self.color_profile.color_for_point((valence, energy))

        self.log(f"Got color {color} for valence {valence} and energy {energy} in track '{track_uri}'", level='DEBUG')

        return color

    def create_color_map_image(self, height: int, width: int) -> List[RGB_Color]:
        """Creates an image of the color map in use.

        :param height: height of the output image in pixels
        :param width: width of the output image in pixels

        :return: RGB image of the color plane as a flat list of pixel tuples, where 0 <= r,g,b <= 255
        """

        image = []
        for y in reversed(range(0, height)):
            for x in range(0, width):
                p_y = normalize(y, 0, height - 1, 0, 1)
                p_x = normalize(x, 0, width - 1, 0, 1)
                color = self.color_profile.color_for_point((p_x, p_y))
                image.append(color)
        return image

    def call_api(self, func: Callable[[], T]) -> T:
        retries = self.max_retries
        while True:
            try:
                return func()
            except ConnectionError as e:
                if retries == 0:
                    raise e
                else:
                    self.error(f"Could not reach Spotify API, retrying {retries} more time(s)", level='WARNING')
                    retries -= 1
