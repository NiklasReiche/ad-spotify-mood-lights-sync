import appdaemon.plugins.hass.hassapi as hass
import math
from functools import partial

import numpy as np
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import requests

from typing import Tuple, List, TypeVar, Callable

Color = Tuple[int, int, int]
Point = Tuple[float, float]
T = TypeVar('T')

DEFAULT_PROFILE = [
    ((0.0, 0.5), (128, 0, 128)),  # disgust - purple
    ((0.0, 1.0), (255, 0, 0)),  # angry - red
    ((0.5, 1.0), (255, 165, 0)),  # alert - orange
    ((1.0, 1.0), (255, 255, 0)),  # happy - yellow
    ((1.0, 0.0), (0, 205, 0)),  # calm - green
    ((0.5, 0.0), (0, 165, 255)),  # relaxed - bluegreen
    ((0.0, 0.0), (0, 0, 255)),  # sad - blue
]
CENTERED_PROFILE = [
    ((0.05, 0.5), (128, 0, 128)),  # disgust - purple
    ((0.25, 0.75), (255, 0, 0)),  # angry - red
    ((0.5, 0.8), (255, 165, 0)),  # alert - orange
    ((0.75, 0.75), (255, 255, 0)),  # happy - yellow
    ((0.7, 0.3), (0, 205, 0)),  # calm - green
    ((0.5, 0.2), (0, 165, 255)),  # relaxed - bluegreen
    ((0.25, 0.25), (0, 0, 255)),  # sad - blue
    ((0.5, 0.5), (255, 241, 224)),  # neutral - neutral
]


class SpotifyMoodLightsSync(hass.Hass):
    """SpotifyMoodLightsSync class."""

    def initialize(self) -> None:
        """Initialize the app and listen for media_player media_content_id changes."""

        self.light = self.args.get('light')
        if not self.light:
            self.error("'light' not specified in app config", level='WARNING')
        self.initial_light_state = None

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
        color_map = []
        color_profile = self.args.get('color_profile', 'default')
        if color_profile == 'default':
            color_map = DEFAULT_PROFILE
        elif color_profile == 'centered':
            color_map = CENTERED_PROFILE
        elif color_profile == 'custom':
            custom_profile = self.args.get('custom_profile')
            if custom_profile:
                try:
                    color_map = [(x['point'], x['color']) for x in custom_profile]
                    assert all([len(p) == 2 and len(c) == 3 for p, c in color_map])
                except (KeyError, AssertionError):
                    self.error("Profile set to 'custom' but 'custom_profile' is malformed. Falling back to the default "
                               "profile", level='WARNING')
                    color_map = DEFAULT_PROFILE
            else:
                self.error("Profile set to 'custom' but no 'custom_profile' specified in app config. Falling back to "
                           "the default profile", level='WARNING')
                color_map = DEFAULT_PROFILE

        self.color_map_points: List[Point] = [x[0] for x in color_map]
        self.color_map_colors: List[Color] = [x[1] for x in color_map]

        # output color map as image for debugging
        color_map_image = self.args.get("color_map_image")
        if color_map_image is not None:
            size = color_map_image.get('size')
            location = color_map_image.get('location')
            if size and location:
                from PIL import Image
                im = Image.fromarray(self.create_2d_color_map(size, size))
                try:
                    im.save(location)
                except OSError as e:
                    self.error(f"could not write image to path {location}. Reason: {e.strerror}", level='WARNING')
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
        except requests.exceptions.ConnectionError as e:
            self.error(f"Could not reach Spotify API, skipping track. Reason: {e}", level='WARNING')
            return

        if len(results['tracks']['items']) == 0:
            self.log(f"Could not find track id for '{title}' by '{artist}'. Searching just by title...", level='INFO')

            try:
                results = self.call_api(partial(self.sp.search, q=f'track:{title}', type='track'))
            except requests.exceptions.ConnectionError as e:
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
        except requests.exceptions.ConnectionError as e:
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

        self.turn_on(self.light, **{'rgb_color': color})

    def color_from_uri(self, track_uri: str) -> Color:
        """Get the color from a spotify track uri."""

        track_features = self.call_api(partial(self.sp.audio_features, track_uri))[0]
        if not track_features:
            raise ValueError("no track features found for uri")

        valence: float = track_features['valence']
        energy: float = track_features['energy']
        color = self.color_for_point((valence, energy))

        self.log(f"Got color {color} for valence {valence} and energy {energy} in track '{track_uri}'", level='DEBUG')

        return color

    def color_for_point(self, point: Point) -> Color:
        """Computes an RGB color value for a point on the color plane.

        :param point: coordinates in the range [0,1]X[0,1]

        :return: interpolated RGB color for the input point as [r, g, b]
        """

        # compute new RGB value as inverse distance weighted sum:
        distances = np.array([math.dist(point, p) for p in self.color_map_points])
        weights = np.expand_dims(1 / (distances + 1E-6), axis=1)
        colors = np.array(self.color_map_colors)

        color = np.sum(colors * weights, axis=0) / np.sum(weights)

        # brighten color spectrum
        sum_color = np.sum(color)
        required_sum_color = 600.0
        if color.max() * (required_sum_color / sum_color) <= 255:
            color *= (required_sum_color / sum_color)
        else:
            color *= (255 / color.max())

        return tuple(color.astype('uint8'))

    def create_2d_color_map(self, height: int, width: int) -> np.array:
        """Creates an image of the color map in use.

        :param height: height of the output image in pixels
        :param width: width of the output image in pixels

        :return: RGB image of the color plane as numpy array with shape (height, width, 3)
        """

        def normalize(v, in_min, in_max, out_min, out_max):
            return (out_max - out_min) / (in_max - in_min) * (v - in_min) + out_min

        image = np.zeros((height, width, 3)).astype('uint8')
        for y in range(0, height):
            for x in range(0, width):
                p_y = normalize(y, 0, height - 1, 0, 1)
                p_x = normalize(x, 0, width - 1, 0, 1)
                color = self.color_for_point((p_x, p_y))
                image[y, x] = color
        return np.flipud(image)

    def save_initial_light_state(self):
        self.initial_light_state = dict(self.get_state(self.light, attribute='all'))

    def restore_initial_light_state(self):
        if self.initial_light_state['state'] == 'on':
            color = self.initial_light_state['attributes'].get('color', None)
            self.turn_on(self.light, **({} if color is None else {'rgb_color': color}))
        elif self.initial_light_state['state'] == 'off':
            self.turn_off(self.light)

    def call_api(self, func: Callable[[], T]) -> T:
        retries = self.max_retries
        while True:
            try:
                return func()
            except requests.exceptions.ConnectionError as e:
                if retries == 0:
                    raise e
                else:
                    self.error(f"Could not reach Spotify API, retrying {retries} more time(s)", level='WARNING')
                    retries -= 1
