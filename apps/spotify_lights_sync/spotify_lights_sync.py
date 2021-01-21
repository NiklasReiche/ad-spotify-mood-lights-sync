import appdaemon.plugins.hass.hassapi as hass
import math

import numpy as np
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from typing import Tuple, List


class SpotifyLightsSync(hass.Hass):
    """SpotifyLightsSync class."""

    def initialize(self):
        """Initialize the app and listen for media_player media_content_id changes."""
        self.light = self.args['light']

        client_credentials_manager = SpotifyClientCredentials(client_id=self.args['client_id'],
                                                              client_secret=self.args['client_secret'])
        self.sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

        self.debug = self.args.get('debug')

        color_map = []
        color_profile = self.args.get('color_profile')
        if color_profile is None or color_profile == 'default':
            color_map = [
                ((0.0, 0.5), (128, 0, 128)),  # disgust - purple
                ((0.0, 1.0), (255, 0, 0)),  # angry - red
                ((0.5, 1.0), (255, 165, 0)),  # alert - orange
                ((1.0, 1.0), (255, 255, 0)),  # happy - yellow
                ((1.0, 0.0), (0, 205, 0)),  # calm - green
                ((0.5, 0.0), (0, 165, 255)),  # relaxed - bluegreen
                ((0.0, 0.0), (0, 0, 255)),  # sad - blue
            ]
        elif color_profile == 'centered':
            color_map = [
                ((0.05, 0.5), (128, 0, 128)),  # disgust - purple
                ((0.25, 0.75), (255, 0, 0)),  # angry - red
                ((0.5, 0.8), (255, 165, 0)),  # alert - orange
                ((0.75, 0.75), (255, 255, 0)),  # happy - yellow
                ((0.7, 0.3), (0, 205, 0)),  # calm - green
                ((0.5, 0.2), (0, 165, 255)),  # relaxed - bluegreen
                ((0.25, 0.25), (0, 0, 255)),  # sad - blue
                ((0.5, 0.5), (255, 241, 224)),  # neutral - neutral
            ]
        elif color_profile == 'custom':
            color_map = [(x['point'], x['color']) for x in self.args['custom_profile']]

        self.color_map_points = [x[0] for x in color_map]
        self.color_map_colors = [x[1] for x in color_map]

        # output color map as image for debugging
        self.color_map_image = self.args.get("color_map_image")
        if self.color_map_image is not None:
            from PIL import Image
            im = Image.fromarray(
                self.create_2d_color_map(self.color_map_image['size'], self.color_map_image['size']))
            im.save(self.color_map_image['location'])

        # register callback
        self.listen_state(self.sync_lights, self.args['media_player'], attribute='media_content_id')

    def sync_lights(self, entity, attribute, old_uri, new_uri, kwargs):
        """Callback when the media_content_id has changed."""
        if new_uri is not None and new_uri != old_uri:
            color = self.color_from_uri(new_uri)
            light_kwargs = {'rgb_color': color}
            self.turn_on(self.light, **light_kwargs)

    def color_from_uri(self, track_uri: str) -> List[int]:
        """Get the color from a spotify track uri."""

        track_features = self.sp.audio_features(track_uri)[0]
        valence = track_features['valence']
        energy = track_features['energy']
        color = self.color_for_point((valence, energy))

        if self.debug:
            self.log(f"Valence: {valence} | Energy: {energy} | Color: {color}")

        return color

    def color_for_point(self, point: Tuple[float, float]) -> List[int]:
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

        return color.astype('uint8').tolist()

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

    def sync_lights_debug(self, point: Tuple[float, float]):
        """Sync the lights directly by specifying a point on the color plane."""
        color = self.color_for_point(point)
        light_kwargs = {'rgb_color': color}
        self.turn_on(self.light, **light_kwargs)
