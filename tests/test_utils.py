import pytest
import re

import requests

TRACKS = {
    "min_min": {"valence": 0, "energy": 0},
    "min_max": {"valence": 0, "energy": 1},
    "max_min": {"valence": 1, "energy": 0},
    "max_max": {"valence": 1, "energy": 1},
    "center": {"valence": 0.5, "energy": 0.5},
}

SONGS = {
    ("song 1", "artist 1"): "min_min",
    ("song 2", "artist 2"): "min_max",
    ("song 1", "artist 2"): "max_max",
}

CUSTOM_PROFILE_LEGACY = [
    {'point': [1, 1], 'color': [0, 0, 255]},
    {'point': [0, 1], 'color': [0, 255, 0]},
    {'point': [1, 0], 'color': [255, 0, 0]},
    {'point': [0, 0], 'color': [255, 255, 0]},
]

CUSTOM_PROFILE_RGB = {
    'color_mode': "rgb",
    'global_weight': 2,
    'sample_data': [
        {'point': [1, 1], 'color': [0, 0, 255]},
        {'point': [0, 1], 'color': [0, 255, 0], 'local_weight': 0.8},
        {'point': [1, 0], 'color': [255, 0, 0], 'local_weight': 2},
        {'point': [0, 0], 'color': [255, 255, 0]},
    ]
}

CUSTOM_PROFILE_HS = {
    'color_mode': "hs",
    'global_weight': 2,
    'sample_data': [
        {'point': [1, 1], 'color': [30, 100]},
        {'point': [1, 1], 'color': [180, 100], 'local_weight': 0.8},
        {'point': [1, 0], 'color': [380, 100], 'local_weight': 2},
        {'point': [0, 0], 'color': [0, 100]},
    ]
}


class NetworkState:
    def __init__(self):
        self.tries = 0
        self.is_on = False
        self.n_errors = -1

    def reset(self):
        self.tries = 0

    def inc(self):
        self.tries += 1
        if self.is_on and (self.n_errors == -1 or self.tries <= self.n_errors):
            raise requests.exceptions.ConnectionError

    def turn_on_errors(self, n_errors=-1):
        self.reset()
        self.n_errors = n_errors
        self.is_on = True

    def turn_off_errors(self):
        self.is_on = False


NETWORK_STATE = NetworkState()


def track_to_point(track_uri):
    return TRACKS[track_uri]['valence'], TRACKS[track_uri]['energy']


def mock_audio_features(_, track_uri):
    NETWORK_STATE.inc()

    if track_uri not in TRACKS:
        return [None]
    return [TRACKS[track_uri]]


def mock_search(_, q, type):
    NETWORK_STATE.inc()

    groups = re.match(r"artist:(.*)track:(.*)", q).groups()
    if len(groups) == 1:
        pass
    else:
        return {'tracks': {
            'items': [{
                'uri': SONGS[(groups[1].strip(), groups[0].strip())]
            }]
        }}


@pytest.fixture
def hass_errors(hass_mocks):
    return lambda: [call[0][0] for call in hass_mocks.hass_functions["error"].call_args_list]
