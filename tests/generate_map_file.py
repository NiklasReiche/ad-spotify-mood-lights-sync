import contextlib
import os
from appdaemontestframework import automation_fixture
from apps.spotify_mood_lights_sync.spotify_mood_lights_sync import SpotifyMoodLightsSync
from test_utils import *


@automation_fixture(SpotifyMoodLightsSync)
def uut(given_that):
    given_that.passed_arg('client_id').is_set_to("_")
    given_that.passed_arg('client_secret').is_set_to("_")
    given_that.passed_arg('media_player').is_set_to('media_player.spotify_test')
    given_that.passed_arg('light').is_set_to('light.test_light')
    given_that.passed_arg('color_profile').is_set_to('default')

    given_that.state_of('light.test_light').is_set_to('on', attributes={'color': (255, 255, 255)})


@pytest.fixture
def update_passed_args(uut):
    @contextlib.contextmanager
    def update_and_init():
        yield
        uut.initialize()

    return update_and_init


class TestImageOutput:
    def test_default_output(self, given_that, update_passed_args):
        with update_passed_args():
            given_that.passed_arg('color_map_image').is_set_to({'size': 200, 'location': './out.png'})

        assert os.path.isfile('./out.png')
