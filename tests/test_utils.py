import pytest
import re

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

CUSTOM_PROFILE = [
    {'point': [0, 0], 'color': [0, 0, 255]},
    {'point': [1, 0], 'color': [0, 255, 0]},
    {'point': [0, 1], 'color': [255, 0, 0]},
    {'point': [1, 1], 'color': [255, 255, 0]},
]


def track_to_point(track_uri):
    return TRACKS[track_uri]['valence'], TRACKS[track_uri]['energy']


def mock_audio_features(_, track_uri):
    return [TRACKS[track_uri]]


def mock_search(_, q, type):
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
