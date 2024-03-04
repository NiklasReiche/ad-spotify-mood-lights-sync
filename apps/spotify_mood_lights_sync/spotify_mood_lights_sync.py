import numbers

from appdaemon.plugins.hass.hassapi import Hass
import math
import colorsys
from functools import partial

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from requests.exceptions import ConnectionError

from typing import Tuple, List, Dict, TypeVar, Callable, Iterable

RGB_Color = Tuple[int, int, int]
HS_Color = Tuple[int, int]
Point = Tuple[float, float]
T = TypeVar('T')
Num = TypeVar('Num', int, float)


class ColorProfile:
    def color_for_point(self, point: Point) -> RGB_Color:
        """Computes an RGB color value for a point on the color plane.

        :param point: coordinates in the range [0,1]X[0,1]

        :return: interpolated RGB color for the input point as [r, g, b] where 0 <= r,g,b <= 255
        """
        pass


class RGBColorProfile(ColorProfile):
    points: List[Point]
    local_weights: List[float]
    channels: Tuple[List[int], List[int], List[int]]

    def __init__(self, config: Dict):
        self.global_weight = config.get('global_weight', 1.0)
        samples: List[Dict] = config.get('sample_data', [])
        self.points = [x.get('point', (0, 0)) for x in samples]
        self.local_weights = [x.get('local_weight', 1.0) for x in samples]
        self.channels = ([x.get('color', (255, 255, 255))[0] for x in samples],
                         [x.get('color', (255, 255, 255))[1] for x in samples],
                         [x.get('color', (255, 255, 255))[2] for x in samples])

    def color_for_point(self, point: Point) -> RGB_Color:
        def mul_array(list_a: Iterable[Num], list_b: Iterable[float]) -> List[float]:
            return [ab[0] * ab[1] for ab in zip(list_a, list_b)]

        def inverse_distance_weights(p: Point, samples: List[Point], local_weights: List[float], global_weight):
            distances = [math.dist(p, s) for s in samples]
            return [1 / ((d + 1E-6) ** (global_weight * w)) for d, w in zip(distances, local_weights)]

        def interpolate(values: List[Num], weights: List[float]):
            return sum(mul_array(values, weights)) / sum(weights)

        precomputed_weights = inverse_distance_weights(point, self.points, self.local_weights,
                                           global_weight=self.global_weight)

        # compute new RGB value as inverse distance weighted sum:
        red = interpolate(self.channels[0], precomputed_weights)
        green = interpolate(self.channels[1], precomputed_weights)
        blue = interpolate(self.channels[2], precomputed_weights)

        # brightness should be max to not conflict with the light's brightness setting (equivalent to HS space)
        return to_max_brightness((int(red), int(green), int(blue)))


class HSColorProfile(ColorProfile):
    mirror_x: bool
    mirror_y: bool
    rotation: Num
    drop_off: float

    def __init__(self, config: Dict):
        self.mirror_x = config.get('mirror_x', False)
        self.mirror_y = config.get('mirror_y', False)
        self.rotation = config.get('rotation', 0)
        self.drop_off = config.get('drop_off', 1)
        pass

    def color_for_point(self, point: Point) -> RGB_Color:
        point = (normalize(point[0], 0.0, 1.0, -1.0, 1.0),
                 normalize(point[1], 0.0, 1.0, -1.0, 1.0))
        # calculate hue from angle to center
        x = point[0] * (-1.0 if self.mirror_x else 1.0)
        y = point[1] * (-1.0 if self.mirror_y else 1.0)
        angle = math.degrees(math.atan2(y, x)) + self.rotation
        # map to [0, 360) degree range
        hue = (angle + 360) % 360

        # calculate saturation as distance to center, clamped to unit circle
        distance = min(math.dist([0.0, 0.0], point), 1.0) ** self.drop_off
        saturation = normalize(distance, 0, 1, 0, 100)

        return hs_to_rgb((int(hue), int(saturation)))


def normalize(v: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    return (out_max - out_min) / (in_max - in_min) * (v - in_min) + out_min


def hs_to_rgb(color: HS_Color) -> RGB_Color:
    """Converts from hs to rgb color space. The resulting color has maximal brightness."""
    color = colorsys.hsv_to_rgb(color[0] / 360.0, color[1] / 100.0, 1.0)
    return int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)


def to_max_brightness(color: RGB_Color) -> RGB_Color:
    """Maximizes the brightness of the given rgb color."""
    hsv = colorsys.rgb_to_hsv(color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)
    rgb = colorsys.hsv_to_rgb(hsv[0], hsv[1], 1.0)  # set max brightness
    return int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)


def create_color_map_image(color_profile: ColorProfile, size: int) -> any:
    """Creates an image of the color map in use.

    :param color_profile: The profile from which to sample colors
    :param size: height and width of the output image in pixels

    :return: Pillow image object of the given color profile
    """

    from PIL import Image
    im = Image.new('RGB', (size, size))
    for y in range(0, size):
        for x in range(0, size):
            p_y = normalize(y, 0, size - 1, 0.0, 1.0)
            p_x = normalize(x, 0, size - 1, 0.0, 1.0)
            color = color_profile.color_for_point((p_x, p_y))
            im.putpixel((x, -y), color)
    return im


PROFILE_DEFAULT = RGBColorProfile({
    'global_weight': 2,
    'sample_data': [
        {
            'point': (0.0, 0.5),
            'color': (128, 0, 128),
            'local_weight': 1
        }, {
            'point': (0.0, 1.0),
            'color': (255, 0, 0),
            'local_weight': 1
        }, {
            'point': (0.5, 1.0),
            'color': (255, 165, 0),
            'local_weight': 1
        }, {
            'point': (1.0, 1.0),
            'color': (255, 255, 0),
            'local_weight': 1
        }, {
            'point': (1.0, 0.0),
            'color': (0, 205, 0),
            'local_weight': 1
        }, {
            'point': (0.5, 0.0),
            'color': (0, 180, 255),
            'local_weight': 1
        }, {
            'point': (0.0, 0.0),
            'color': (0, 0, 255),
            'local_weight': 1
        }
    ]
})

PROFILE_SATURATED = HSColorProfile({
    'mirror_x': True,
    'mirror_y': False,
    'rotation': -60,
    'drop_off': 0.0,
})


class SpotifyMoodLightsSync(Hass):
    """SpotifyMoodLightsSync class."""

    light: str
    sp: spotipy.Spotify
    max_retries: int
    color_profile: ColorProfile
    enabled: bool = True

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
        if color_profile_arg == 'default' or color_profile_arg == 'centered':  # legacy option for centered
            self.color_profile = PROFILE_DEFAULT
        elif color_profile_arg == 'saturated':
            self.color_profile = PROFILE_SATURATED
        elif color_profile_arg == 'custom':
            self.color_profile = self.parse_custom_profile()
        else:
            self.error(f"Unknown profile '{color_profile_arg}'. Falling back to the default profile",
                       level='WARNING')
            self.color_profile = PROFILE_DEFAULT

        # output color map as image for debugging
        color_map_image = self.args.get("color_map_image")
        if color_map_image is not None:
            size = color_map_image.get('size')
            location = color_map_image.get('location')
            if size and location:
                im = create_color_map_image(self.color_profile, size)
                try:
                    im.save(location)
                except OSError as e:
                    self.error(f"Could not write image to path '{location}'. Reason: {e.strerror}",
                               level='WARNING')
            else:
                self.error("'color_map_image' specified, but 'size' or 'location' not specified in app config. "
                           "Skipping image generation", level='WARNING')

        # Register enable/disable callback
        enable_switch = self.args.get('enable_switch')
        if enable_switch:
            self.enabled = self.get_state(enable_switch) == 'on'
            self.listen_state(self.enable_disable, enable_switch, attribute='all')

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

    def enable_disable(self, _entity: str, _attribute: str, old: dict, new: dict, _kwargs):
        self.enabled = new.get('state') == 'on'

    def parse_custom_profile(self) -> ColorProfile:
        def parse_legacy() -> RGBColorProfile:
            data = [{'point': x['point'], 'color': x['color'], 'local_weight': 1.0} for x in custom_profile]

            assert len(data) > 0
            assert all([len(x['point']) == 2 and len(x['color']) == 3 and
                        0 <= x['point'][0] <= 1 and 0 <= x['point'][1] <= 1 and
                        0 <= x['color'][0] <= 255 and 0 <= x['color'][1] <= 255 and 0 <= x['color'][2] <= 255
                        for x in data])

            return RGBColorProfile({
                'global_weight': 1.0,
                'sample_data': data
            })

        def parse_rgb() -> RGBColorProfile:
            config = {
                'global_weight': custom_profile.get('global_weight', 1.0),
                'sample_data': [{
                    'point': x['point'],
                    'color': x['color'],
                    'local_weight': x.get('local_weight', 1.0)
                } for x in custom_profile['sample_data']]
            }

            assert len(config['sample_data']) > 0
            assert all([(isinstance(x['local_weight'], numbers.Number) and
                         len(x['point']) == 2 and len(x['color']) == 3 and
                         0 <= x['point'][0] <= 1 and 0 <= x['point'][1] <= 1 and
                         0 <= x['color'][0] <= 255 and 0 <= x['color'][1] <= 255 and 0 <= x['color'][2] <= 255)
                        for x in config['sample_data']])

            return RGBColorProfile(config)

        def parse_hs() -> HSColorProfile:
            config = {
                'mirror_x': custom_profile.get('mirror_x', False),
                'mirror_y': custom_profile.get('mirror_y', False),
                'rotation': custom_profile.get('rotation', 0),
                'drop_off': custom_profile.get('drop_off', 1),
            }

            assert isinstance(config['mirror_x'], bool)
            assert isinstance(config['mirror_y'], bool)
            assert isinstance(config['rotation'], numbers.Number)
            assert config['drop_off'] >= 0

            return HSColorProfile(config)

        custom_profile = self.args.get('custom_profile')
        try:
            if type(custom_profile) is list:  # legacy config, assume RGB values without weights
                self.error("Using deprecated custom_profile config format. See README for new format.",
                           level='WARNING')
                return parse_legacy()
            elif custom_profile:
                mode = custom_profile.get('color_mode')
                if mode == 'rgb':
                    return parse_rgb()
                elif mode == 'hs':
                    return parse_hs()
                else:
                    self.error(
                        f"Unknown color mode '{mode}' in 'custom_profile'. Must be 'rgb' or 'hs'. Falling back to"
                        f" the default profile", level='WARNING')
                    return PROFILE_DEFAULT
            else:
                self.error("Profile set to 'custom' but no 'custom_profile' specified in app config. Falling back"
                           " to the default profile", level='WARNING')
                return PROFILE_DEFAULT
        except (KeyError, AssertionError):
            self.error("Profile set to 'custom' but 'custom_profile' is malformed. Falling back to the default"
                       " profile", level='WARNING')
            return PROFILE_DEFAULT

    def sync_lights_from_spotify(self, _entity: str, _attribute: str, old_uri: str, new_uri: str, _kwargs) -> None:
        if new_uri is None or old_uri == new_uri or not self.enabled:
            return

        self.sync_light(new_uri)

    def sync_lights_from_search(self, _entity: str, _attribute: str, old: dict, new: dict, _kwargs) -> None:
        if not self.enabled:
            return
        
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
            self.log(f"Could not find track id for '{title}' by '{artist}'. Searching just by title...",
                     level='INFO')

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

        self.log(f"Got color {color} for valence {valence} and energy {energy} in track '{track_uri}'",
                 level='DEBUG')

        return color

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
