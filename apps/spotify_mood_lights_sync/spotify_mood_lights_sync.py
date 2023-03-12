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
HSV_Color = Tuple[int, int, int]
HS_Color = Tuple[int, int]
Point = Tuple[float, float]
T = TypeVar('T')
Num = TypeVar('Num', int, float)

DEFAULT_PROFILE = [
    ((0.0, 0.5), (128, 0, 128), 1.0),  # disgust - purple
    ((0.0, 1.0), (255, 0, 0), 1.0),  # angry - red
    ((0.5, 1.0), (255, 165, 0), 1.0),  # alert - orange
    ((1.0, 1.0), (255, 255, 0), 1.0),  # happy - yellow
    ((1.0, 0.0), (0, 205, 0), 1.0),  # calm - green
    ((0.5, 0.0), (0, 165, 255), 1.0),  # relaxed - bluegreen
    ((0.0, 0.0), (0, 0, 255), 1.0),  # sad - blue
]
CENTERED_PROFILE = [
    ((0.05, 0.5), (128, 0, 128), 2.0),  # disgust - purple
    ((0.25, 0.75), (255, 0, 0), 2.0),  # angry - red
    ((0.5, 0.8), (255, 165, 0), 2.0),  # alert - orange
    ((0.75, 0.75), (255, 255, 0), 2.0),  # happy - yellow
    ((0.7, 0.3), (0, 205, 0), 2.0),  # calm - green
    ((0.5, 0.2), (0, 165, 255), 2.0),  # relaxed - bluegreen
    ((0.25, 0.25), (0, 0, 255), 2.0),  # sad - blue
]
HS_DEFAULT_PROFILE = [
    ((0.0, 0.5), (300, 100), 1.0),  # disgust - purple
    ((0.0, 1.0), (0, 100), 1.0),  # angry - red
    ((0.5, 1.0), (40, 100), 1.0),  # alert - orange
    ((1.0, 1.0), (60, 100), 1.0),  # happy - yellow
    ((1.0, 0.5), (90, 100), 1.0),
    ((1.0, 0.0), (120, 100), 1.0),  # calm - green
    ((0.5, 0.0), (200, 100), 1.0),  # relaxed - bluegreen
    ((0.0, 0.0), (240, 100), 1.0),  # sad - blue
]


class ColorMode(Enum):
    RGB = 'RGB'
    HS = 'HS'


class ColorProfile:
    def __init__(self, color_mode, data, weight=1):
        self.color_mode = color_mode
        self.global_weight = weight
        self.points: List[Point] = [x[0] for x in data]
        self.local_weights: List[float] = [x[2] for x in data]
        if color_mode == ColorMode.RGB:
            self.channels: Tuple[List[int], List[int], List[int]] | Tuple[List[int], List[int]] = \
                ([x[1][0] for x in data],
                 [x[1][1] for x in data],
                 [x[1][2] for x in data])
        if color_mode == ColorMode.HS:
            self.channels: Tuple[List[int], List[int], List[int]] | Tuple[List[int], List[int]] = \
                ([x[1][0] for x in data],
                 [x[1][1] for x in data])


class RGBColorProfile(ColorProfile):
    def __init__(self, data, weight=2.0):
        super().__init__(ColorMode.RGB, data, weight)


class HSColorProfile(ColorProfile):
    def __init__(self, data, weight=1.5):
        super().__init__(ColorMode.HS, data, weight)


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


def rgb_to_hsv(color: RGB_Color) -> RGB_Color:
    color = colorsys.rgb_to_hsv(
        normalize(color[0], 0, 255, 0, 1),
        normalize(color[1], 0, 255, 0, 1),
        normalize(color[2], 0, 255, 0, 1))

    return int(normalize(color[0], 0, 1, 0, 360)), \
        int(normalize(color[1], 0, 1, 0, 100)), \
        int(normalize(color[2], 0, 1, 0, 100))


def hsv_to_rgb(color: RGB_Color) -> RGB_Color:
    color = colorsys.hsv_to_rgb(
        normalize(color[0], 0, 360, 0, 1),
        normalize(color[1], 0, 100, 0, 1),
        normalize(color[2], 0, 100, 0, 1))

    return int(normalize(color[0], 0, 1, 0, 255)), \
        int(normalize(color[1], 0, 1, 0, 255)), \
        int(normalize(color[2], 0, 1, 0, 255))


def hsv_to_hs(color: HSV_Color) -> HS_Color:
    return color[0], color[1]


class SpotifyMoodLightsSync(hass.Hass):
    """SpotifyMoodLightsSync class."""

    def initialize(self) -> None:
        """Initialize the app and listen for media_player media_content_id changes."""

        # setup light
        self.light = self.args.get('light')
        if not self.light:
            self.error("'light' not specified in app config", level='WARNING')

        self.initial_light_state = None

        try:
            self.light_color_mode = self.args.get('light_color_mode', 'rgb')
            assert self.light_color_mode == 'rgb' or self.light_color_mode == 'hs'
        except AssertionError:
            self.error(f"Unknown value '{self.light_color_mode}' for 'light_color_mode'. Must be 'rgb' or 'hs'.",
                       level='ERROR')

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
        if color_profile_arg == 'default':
            self.color_profile = RGBColorProfile(DEFAULT_PROFILE)
        elif color_profile_arg == 'centered':
            self.color_profile = RGBColorProfile(CENTERED_PROFILE)
        elif color_profile_arg == 'hs_default':
            self.color_profile = HSColorProfile(HS_DEFAULT_PROFILE)
        elif color_profile_arg == 'custom':
            custom_profile = self.args.get('custom_profile')
            if type(custom_profile) is list:  # legacy config, assume RGB values without weights
                self.error("Using deprecated custom_profile config format. See README for new format.", level='WARNING')
                try:
                    data = [(x['point'], x['color'], x.get('weight', 1.0)) for x in custom_profile]

                    assert len(data) > 0
                    assert all([len(p) == 2 and len(c) == 3 for p, c, w in data])
                    assert all([0 <= p[0] <= 1 and 0 <= p[1] <= 1 for p, c, w in data])
                    assert all([0 <= c[0] <= 255 and 0 <= c[1] <= 255 and 0 <= c[2] <= 255 for p, c, w in data])

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

        # if new_uri is None:
        #    if self.initial_light_state is not None:
        #        self.restore_initial_light_state()
        #        self.initial_light_state = None
        #    return

        # if self.initial_light_state is None:
        #    self.save_initial_light_state()

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

        if self.light_color_mode == 'rgb':
            if self.color_profile.color_mode == ColorMode.HS:
                color = hsv_to_rgb(color)
            self.turn_on(self.light, **{'rgb_color': color})
        elif self.light_color_mode == 'hs':
            if self.color_profile.color_mode == ColorMode.RGB:
                color = rgb_to_hsv(color)
            self.turn_on(self.light, **{'hs_color': hsv_to_hs(color)})
        else:
            self.error(f"Unknown color mode '{self.light_color_mode}' for turn_on service on light entity",
                       level='ERROR')

    def color_from_uri(self, track_uri: str) -> RGB_Color | HSV_Color:
        """Get the color from a spotify track uri."""

        track_features = self.call_api(partial(self.sp.audio_features, track_uri))[0]
        if not track_features:
            raise ValueError("no track features found for uri")

        valence: float = track_features['valence']
        energy: float = track_features['energy']
        if self.color_profile.color_mode == ColorMode.RGB:
            color = self.color_for_point_rgb((valence, energy))
        elif self.color_profile.color_mode == ColorMode.HS:
            color = self.color_for_point_hsv((valence, energy))
        else:
            raise ValueError("unknown color mode")

        self.log(f"Got color {color} for valence {valence} and energy {energy} in track '{track_uri}'", level='DEBUG')

        return color

    def color_for_point_rgb(self, point: Point) -> RGB_Color:
        """Computes an RGB color value for a point on the color plane.

        :param point: coordinates in the range [0,1]X[0,1]

        :return: interpolated RGB color for the input point as [r, g, b] where 0 <= r,g,b <= 255
        """

        weights = inverse_distance_weights(point, self.color_profile.points, self.color_profile.local_weights,
                                           global_weight=self.color_profile.global_weight)

        # compute new RGB value as inverse distance weighted sum:
        red = interpolate(self.color_profile.channels[0], weights)
        green = interpolate(self.color_profile.channels[1], weights)
        blue = interpolate(self.color_profile.channels[2], weights)
        color = (red, green, blue)

        # brighten color spectrum
        sum_color, max_color = sum(color), max(color)
        required_sum_color = 700.0
        if max_color * (required_sum_color / sum_color) <= 255:
            color = mul_scalar(color, required_sum_color / sum_color)
        else:
            color = mul_scalar(color, 255 / max_color)

        return int(color[0]), int(color[1]), int(color[2])

    def color_for_point_hsv(self, point: Point) -> HSV_Color:
        """Computes an HSV color value for a point on the color plane.

        :param point: coordinates in the range [0,1]X[0,1]

        :return: interpolated HSV color for the input point as [h, s, v], where 0 <= h <= 360 and 0 <= s <= 100, v = 100
        """

        weights = inverse_distance_weights(point, self.color_profile.points, self.color_profile.local_weights,
                                           global_weight=self.color_profile.global_weight)

        # compute saturation with IDW:
        saturation = min(100., interpolate(self.color_profile.channels[1], weights))

        # compute hue angle with IDW in cartesian coordinates:
        hues_cart_x = [math.sin(math.radians(h)) for h in self.color_profile.channels[0]]
        hues_cart_y = [math.cos(math.radians(h)) for h in self.color_profile.channels[0]]
        hue_x = interpolate(hues_cart_x, weights)
        hue_y = interpolate(hues_cart_y, weights)
        hue = math.degrees(math.atan2(hue_x, hue_y))
        hue = 360 + hue if hue < 0 else hue

        assert 0 <= hue <= 360
        assert 0 <= saturation <= 100

        return int(hue), int(saturation), 100

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
                if self.color_profile.color_mode == ColorMode.RGB:
                    color = self.color_for_point_rgb((p_x, p_y))
                elif self.color_profile.color_mode == ColorMode.HS:
                    color = hsv_to_rgb(self.color_for_point_hsv((p_x, p_y)))
                else:
                    raise Exception("unknown color mode")
                image.append(color)
        return image

    def save_initial_light_state(self):
        self.initial_light_state = dict(self.get_state(self.light, attribute='all'))

    def restore_initial_light_state(self):
        if self.initial_light_state['state'] == 'on':
            color = self.initial_light_state['attributes'].get('color', None)
            self.turn_on(self.light, **({} if color is None else {'rgb_color': color}))  # TODO
        elif self.initial_light_state['state'] == 'off':
            self.turn_off(self.light)

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
