import contextlib
import pytest
import os
from appdaemontestframework import automation_fixture
from apps.spotify_mood_lights_sync.spotify_mood_lights_sync import SpotifyMoodLightsSync
from spotipy import Spotify
from unittest.mock import patch

TRACKS = {
    "min_min": {"valence": 0, "energy": 0},
    "min_max": {"valence": 0, "energy": 1},
    "max_min": {"valence": 1, "energy": 0},
    "max_max": {"valence": 1, "energy": 1},
    "center": {"valence": 0.5, "energy": 0.5},
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


@automation_fixture(SpotifyMoodLightsSync)
def uut(given_that):
    given_that.passed_arg('client_id').is_set_to("_")
    given_that.passed_arg('client_secret').is_set_to("_")
    given_that.passed_arg('media_player').is_set_to('media_player.spotify_test')
    given_that.passed_arg('light').is_set_to('light.test_light')


@automation_fixture(SpotifyMoodLightsSync)
def uut_empty():
    pass


@pytest.fixture
def hass_errors(hass_mocks):
    return lambda: [call[0][0] for call in hass_mocks.hass_functions["error"].call_args_list]


@pytest.fixture
def update_passed_args(uut):
    @contextlib.contextmanager
    def update_and_init():
        yield
        uut.initialize()

    return update_and_init


@pytest.fixture
def media_player(uut, given_that):
    class UpdateState:
        def __init__(self, entity):
            self.entity = entity
            self.old_uri = None

        def update_state(self, state, attributes):
            given_that.state_of(self.entity).is_set_to(state, attributes)
            new_uri = attributes.get('media_content_id', None)
            uut.sync_lights(self.entity, 'media_content_id', self.old_uri, new_uri, None)
            self.old_uri = new_uri

    return UpdateState


class TestCallbacksAreSet:
    def test_min_config(self, given_that, uut, assert_that):
        assert_that(uut). \
            listens_to.state('media_player.spotify_test', attribute='media_content_id'). \
            with_callback(uut.sync_lights)

    def test_custom_config(self, given_that, uut, assert_that, update_passed_args):
        with update_passed_args():
            given_that.passed_arg('color_profile').is_set_to('custom')
            given_that.passed_arg('custom_profile').is_set_to(CUSTOM_PROFILE)

        assert_that(uut). \
            listens_to.state('media_player.spotify_test', attribute='media_content_id'). \
            with_callback(uut.sync_lights)


class TestColorChange:
    @patch.object(Spotify, 'audio_features', new=mock_audio_features)
    def test_change(self, given_that, media_player, assert_that, uut):
        media_player('media_player.spotify_test').update_state('playing', {'media_content_id': 'min_min'})
        color1 = uut.color_for_point(track_to_point('min_min'))
        assert_that('light.test_light').was.turned_on(rgb_color=color1)

        given_that.mock_functions_are_cleared()

        media_player('media_player.spotify_test').update_state('playing', {'media_content_id': 'min_max'})
        color2 = uut.color_for_point(track_to_point('min_max'))
        assert_that('light.test_light').was.turned_on(rgb_color=color2)

        assert color1 != color2

    @patch.object(Spotify, 'audio_features', new=mock_audio_features)
    def test_skip_on_same_attribute(self, hass_mocks, given_that, media_player):
        player = media_player('media_player.spotify_test')
        player.update_state('playing', {'media_content_id': 'min_min'})
        player.update_state('playing', {'media_content_id': 'min_min'})
        player.update_state('playing', {'media_content_id': 'min_min'})

        assert len(hass_mocks.hass_functions["turn_on"].call_args_list) == 1

    @patch.object(Spotify, 'audio_features', new=mock_audio_features)
    def test_turn_off(self, hass_mocks, given_that, media_player, assert_that):
        player = media_player('media_player.spotify_test')
        player.update_state('playing', {'media_content_id': 'min_min'})
        assert len(hass_mocks.hass_functions["turn_on"].call_args_list) == 1

        given_that.mock_functions_are_cleared()

        player.update_state('off', {})
        assert_that('light.test_light').was_not.turned_on()

    @patch.object(Spotify, 'audio_features', new=mock_audio_features)
    def test_custom_color_profile(self, given_that, media_player, assert_that, update_passed_args):
        with update_passed_args():
            given_that.passed_arg('color_profile').is_set_to('custom')
            given_that.passed_arg('custom_profile').is_set_to(CUSTOM_PROFILE)

        media_player('media_player.spotify_test').update_state('playing', {'media_content_id': 'min_min'})
        assert_that('light.test_light').was.turned_on(rgb_color=(0, 0, 255))

        given_that.mock_functions_are_cleared()

        media_player('media_player.spotify_test').update_state('playing', {'media_content_id': 'min_max'})
        assert_that('light.test_light').was.turned_on(rgb_color=(255, 0, 0))


# TODO: find a way to check that the callback was _not_ registered
class TestSetupErrors:
    @pytest.fixture
    def update_passed_args_empty(self, uut_empty):
        @contextlib.contextmanager
        def update_and_init():
            yield
            uut_empty.initialize()

        return update_and_init

    def test_missing_client_id(self, given_that, assert_that, update_passed_args_empty, hass_errors, uut_empty):
        with update_passed_args_empty():
            given_that.passed_arg('client_secret').is_set_to('_')
            given_that.passed_arg('media_player').is_set_to('media_player.spotify_test')
            given_that.passed_arg('light').is_set_to('light.test_light')

        assert len(hass_errors()) == 1

    def test_missing_client_secret(self, given_that, assert_that, update_passed_args_empty, hass_errors, uut_empty):
        with update_passed_args_empty():
            given_that.passed_arg('client_id').is_set_to('_')
            given_that.passed_arg('media_player').is_set_to('media_player.spotify_test')
            given_that.passed_arg('light').is_set_to('light.test_light')

        assert len(hass_errors()) == 1

    def test_missing_media_player(self, given_that, assert_that, update_passed_args_empty, hass_errors, uut_empty):
        with update_passed_args_empty():
            given_that.passed_arg('client_id').is_set_to('_')
            given_that.passed_arg('client_secret').is_set_to('_')
            given_that.passed_arg('light').is_set_to('light.test_light')

        assert len(hass_errors()) == 1

    def test_missing_light(self, given_that, assert_that, update_passed_args_empty, hass_errors, uut_empty):
        with update_passed_args_empty():
            given_that.passed_arg('client_id').is_set_to('_')
            given_that.passed_arg('client_secret').is_set_to('_')
            given_that.passed_arg('media_player').is_set_to('media_player.spotify_test')

        assert len(hass_errors()) == 1


class TestImageOutput:
    def test_default_output(self, given_that, update_passed_args):
        with update_passed_args():
            given_that.passed_arg('color_map_image').is_set_to({'size': 50, 'location': './out.png'})

        assert os.path.isfile('./out.png')

        if os.path.isfile('./out.png'):
            os.remove('./out.png')
