import contextlib
from appdaemontestframework import automation_fixture
from apps.spotify_mood_lights_sync.spotify_mood_lights_sync import SpotifyMoodLightsSync
from spotipy import Spotify
from unittest.mock import patch
from test_utils import *


@automation_fixture(SpotifyMoodLightsSync)
def uut(given_that):
    given_that.passed_arg('client_id').is_set_to("_")
    given_that.passed_arg('client_secret').is_set_to("_")
    given_that.passed_arg('media_player').is_set_to('media_player.generic_test')
    given_that.passed_arg('light').is_set_to('light.test_light')
    given_that.passed_arg('mode').is_set_to('search')

    given_that.state_of('light.test_light').is_set_to('on', attributes={'color': (255, 255, 255)})


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
            self.old_state = {'state': 'off', 'attributes': {}}

        def update_state(self, state, attributes):
            given_that.state_of(self.entity).is_set_to(state, attributes)
            new_state = {'state': state, 'attributes': attributes}
            uut.sync_lights_from_search(self.entity, None, self.old_state, new_state, None)
            self.old_state = new_state

    return UpdateState


class TestCallbacksAreSet:
    def test_min_config(self, given_that, uut, assert_that):
        assert_that(uut). \
            listens_to.state('media_player.generic_test', attribute='all'). \
            with_callback(uut.sync_lights_from_search)


class TestColorChange:
    @patch.object(Spotify, 'audio_features', new=mock_audio_features)
    @patch.object(Spotify, 'search', new=mock_search)
    def test_change(self, given_that, media_player, assert_that, uut):
        media_player('media_player.generic_test').update_state('playing', {'media_title': 'song 1',
                                                                           'media_artist': 'artist 1'})
        color1 = uut.color_for_point(track_to_point('min_min'))
        assert_that('light.test_light').was.turned_on(rgb_color=color1)

        given_that.mock_functions_are_cleared()

        media_player('media_player.generic_test').update_state('playing', {'media_title': 'song 2',
                                                                           'media_artist': 'artist 2'})
        color2 = uut.color_for_point(track_to_point('min_max'))
        assert_that('light.test_light').was.turned_on(rgb_color=color2)

        media_player('media_player.generic_test').update_state('playing', {'media_title': 'song 1',
                                                                           'media_artist': 'artist 2'})
        color3 = uut.color_for_point(track_to_point('max_max'))
        assert_that('light.test_light').was.turned_on(rgb_color=color3)

        assert color1 != color2
        assert color2 != color3
        assert color3 != color1

    @patch.object(Spotify, 'audio_features', new=mock_audio_features)
    @patch.object(Spotify, 'search', new=mock_search)
    def test_skip_on_same_attribute(self, hass_mocks, given_that, media_player):
        player = media_player('media_player.generic_test')
        player.update_state('playing', {'media_title': 'song 1', 'media_artist': 'artist 1'})
        player.update_state('playing', {'media_title': 'song 1', 'media_artist': 'artist 1'})
        player.update_state('playing', {'media_title': 'song 1', 'media_artist': 'artist 1'})

        assert len(hass_mocks.hass_functions["turn_on"].call_args_list) == 1

    @patch.object(Spotify, 'audio_features', new=mock_audio_features)
    @patch.object(Spotify, 'search', new=mock_search)
    def test_attributes_not_supported(self, hass_mocks, given_that, media_player):
        player = media_player('media_player.generic_test')
        player.update_state('playing', {'title': 'song 1 by artist 1'})

        assert len(hass_mocks.hass_functions["turn_on"].call_args_list) == 0
