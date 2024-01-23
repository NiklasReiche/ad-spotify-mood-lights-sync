# Spotify Mood Lights Sync

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs) [![GitHub Workflow Status](https://img.shields.io/github/workflow/status/NiklasReiche/ad-spotify-mood-lights-sync/Validate?style=for-the-badge)](https://github.com/NiklasReiche/ad-spotify-mood-lights-sync/actions)

_AppDaemon app that synchronizes rgb lights to the mood of the currently playing song in Home Assistant._

## About

This app uses the Spotify API to extract the emotional mood value of the currently playing track. Each mood value lies
on a 2D plane which is mapped to a color spectrum from which the color for the light is picked.

The built-in color maps used by the app look as follows. The horizontal axis ranges from negative (left) to positive
(right) emotion while the vertical axis ranges from low (bottom) to high (top) energy. A sad, slow song is thus mapped
to blue light while a happy, upbeat song is mapped to yellow light.

<img src="https://github.com/NiklasReiche/ha-spotify-lights-sync/blob/master/profiles.png" alt="color profiles" width=500>

## Prerequisites

For this app to work, the following python package must be installed in the [AppDaemon environment](https://github.com/hassio-addons/addon-appdaemon/blob/main/appdaemon/DOCS.md#configuration):

```yaml
python_packages:
  - spotipy
```

## Installation

Use [HACS](https://hacs.xyz/) or download the `spotify_mood_lights_sync` directory from inside the `apps` directory here
to your local `apps` directory, then add the configuration to your `/config/appdaemon/apps/apps.yaml`.

## Minimal configuration

The following shows a minimal example configuration (the spotify credentials are supplied via a secrets file here):

```yaml
spotify_mood_lights_sync:
  module: spotify_mood_lights_sync
  class: SpotifyMoodLightsSync
  client_id: !secret spotify_client_id
  client_secret: !secret spotify_client_secret
  media_player: media_player.spotify_johndoe
  light: light.bedroom
```

## Conditional execution

You can switch the light synchronization on and off through Home Assistant by using
AppDaemon [Callback Constraints](https://appdaemon.readthedocs.io/en/latest/APPGUIDE.html#hass-plugin-constraints). For
example, you can control the execution with an `input_boolean` switch:

```yaml
spotify_lights_sync:
  constrain_input_boolean: input_boolean.spotify_lights_sync_toggle
```

## Lights

The app expects a single entity name for the `light` option. If you want to control multiple lights at once, you have to
create a group in Home Assistant and provide the group entity for the `light` option.

The app only deals with the color attributes of the lights, leaving the brightness untouched. You can therefore control 
the brightness of your lights independently.

## Spotify

The app queries information from Spotify using the client id and client secret of a Spotify-Develop App for 
authentication. You can use the same values here that you use for the Spotify integration in Home Assistant. 

## Media Players

The app supports media players from the spotify integration as well as generic media players.

### Spotify media player (direct mode)

Using a spotify media player is the default and thus no special config options must be set. Note that only the 
media players directly provided by the spotify integration will work in this mode.<sup id="sp-player">[1](#sp-player-note)</sup>
For other integrations, e.g. Sonos speakers, this may not work, and you should use 
[search mode](#generic-media-player-search-mode) instead.

Since the Spotify integration in Home Assistant only polls the Spotify API every 30 seconds to detect when the currently
playing song changes, the light synchronization may be delayed by up to 30 seconds in the worst case.

<b id="sp-player-note">[1](#sp-player)</b>: This mode is reliant on the `media_content_id` attribute of the 
`media_player` containing the spotify track id (e.g. `spotify:track:abcdefghijkl`) for the current song. If your 
non-spotify media player supports this, you can also use direct mode.

### Generic media player (search mode)

The app can also listen on all non-spotify media players that support the `media_title` and `media_artist` state
attributes. In order to use such a player, add the `mode: search` option to the app config. In this mode the app tries
to find the corresponding track in Spotify by title and artist before calculating the mood.

If a track cannot be found in Spotify the light will not be synced for that song.

## Full app configuration

| key                                       | optional | type    | default   | description                                                                                                                                                                                                     |
|-------------------------------------------|----------|---------|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `module`                                  | False    | string  |           | The module name of the app. Must be `spotify_mood_lights_sync`.                                                                                                                                                 |
| `class`                                   | False    | string  |           | The name of the Class. Must be `SpotifyMoodLightsSync`.                                                                                                                                                         |
| `client_id`                               | False    | string  |           | The client id of the Spotify-For-Developers app to use for accessing the Spotify API.                                                                                                                           |
| `client_secret`                           | False    | string  |           | The client secret of the Spotify-For-Developers app to use for accessing the Spotify API.                                                                                                                       |
| `media_player`                            | False    | string  |           | The entity_id of the media player to sync from.                                                                                                                                                                 |
| `light`                                   | False    | string  |           | The entity_id of the light or light group to sync.                                                                                                                                                              |
| `color_profile`                           | True     | string  | `default` | The color profile to use for mapping moods to colors. Possible values are `default`, `saturated`, or `custom`. When `custom` is specified, the color map will be built from the parameters in `custom_profile`. |
| `mode`                                    | True     | string  | `direct`  | Possible values are `direct` or `search`. Use `search` if you want to use a non-spotify `media_player`. Use `direct` when using a spotify `media_player`.                                                       |
| `max_retries`                             | True     | number  | `1`       | Number of times a Spotify API call should be retried after a connection error before the track is skipped.                                                                                                      |
| `custom_profile`                          | True     | object  |           | Parameters to use for the `custom` `color_profile`. See `Custom color profile` section.                                                                                                                         |
| `custom_profile.color_mode`               | False    | string  |           | Possible values are 'rgb' or 'hs'. See `Custom color profile` section.                                                                                                                                          |
| `custom_profile.global_weight`            | True     | number  | `1`       | Used in 'rgb' mode. Weight applied to all sampling points. See `Custom color profile` section.                                                                                                                  |
| `custom_profile.sample_data`              | False    | object  |           | Used in 'rgb' mode. Sample data consisting of point-color pairs. See `Custom color profile` section.                                                                                                            |
| `custom_profile.sample_data.point`        | False    | tuple   |           | Used in 'rgb' mode. A point in the [0, 1]X[0, 1] range. See `Custom color profile` section.                                                                                                                     |
| `custom_profile.sample_data.color`        | False    | tuple   |           | Used in 'rgb' mode. An RGB color value in the [0,255] range for each channel. See `Custom color profile` section.                                                                                               |
| `custom_profile.sample_data.local_weight` | True     | number  | `1`       | Used in 'rgb' mode. Weight applied to the sample point. See `Custom color profile` section.                                                                                                                     |
| `custom_profile.mirror_x`                 | True     | boolean | `False`   | Used in 'hs' mode. Mirrors the hue angle in the x direction. See `Custom color profile` section.                                                                                                                |
| `custom_profile.mirror_y`                 | True     | boolean | `False`   | Used in 'hs' mode. Mirrors the hue angle in the y direction. See `Custom color profile` section.                                                                                                                |
| `custom_profile.rotation`                 | True     | number  | `0`       | Used in 'hs' mode. Rotates the hue angle. See `Custom color profile` section.                                                                                                                                   |
| `custom_profile.drop_off`                 | True     | number  | `1`       | Used in 'hs' mode. How fast the saturation drops off towards the center (0 for no saturation loss). See `Custom color profile` section.                                                                         |
| `color_map_image`                         | True     | object  |           | Output the color map as an image for debugging.                                                                                                                                                                 |
| `color_map_image.size`                    | False    | number  |           | Size (height=width) of the output image in pixels.                                                                                                                                                              |
| `color_map_image.location`                | False    | string  |           | Path to which the image should be saved.                                                                                                                                                                        |

## Custom color profile

You can create your own color profile for the app to use by specifying the `custom_profile` app argument and
setting `color_profile` to `custom`.
The mood of a song is a 2-dimensional value in the range `[0.0,1.0]`x`[0.0,1.0]` where the first axis is 
the valence, and the second axis the energy of the song. In general, the color value for a song is then sampled from a 
color field based on where the mood value of that song lies on the 2D plane. See the [Spotify API](https://developer.spotify.com/documentation/web-api/reference/#object-audiofeaturesobject) for more 
information on these values.

Color profiles use either the RGB or the HS color space with different methods for sampling colors, respectively. While 
RGB profiles perform an IDW interpolation, HS profiles simply map the positional information to a color circle. 
Therefore, the `custom_profile` profiles takes a different set of parameters depending on which option is given for 
`custom_profile.color_mode`.

### RGB Profiles
In order to create an RGB color map the app expects a list of 2D sample points with a corresponding RGB color for each point.
For a given point on the mood plane, the color is then interpolated between the given sample points. 
To give individual samples more weight you can add the `custom_profile.sample_data.local_weight` option to any point-color pair. 
Additionally, the `custom_profile.global_weight` option gets applied to all points. 
A higher weight value effectively increases the influence radius of a color sample.
For reference, the following section replicates the default profile:
```yaml
spotify_mood_lights_sync:
  color_profile: custom
  custom_profile:
    'color_mode': rgb
    'global_weight': 2
    'sample_data':
      - 'point': [0.0, 0.5]
        'color': [128, 0, 128]
        'local_weight': 1
      - 'point': [0.0, 1.0]
        'color': [255, 0, 0]
        'local_weight': 1
      - 'point': [0.5, 1.0]
        'color': [255, 165, 0]
        'local_weight': 1
      - 'point': [1.0, 1.0]
        'color': [255, 255, 0]
        'local_weight': 1
      - 'point': [1.0, 0.0]
        'color': [0, 205, 0]
        'local_weight': 1
      - 'point': [0.5, 0.0]
        'color': [0, 180, 255]
        'local_weight': 1
      - 'point': [0.0, 0.0]
        'color': [0, 0, 255]
        'local_weight': 1
```

### HS Profiles
For HS profiles, the app calculates the angle and distance of the query point to the center of the mood plane. The angle
gets mapped to a hue value while the distance maps to a saturation value. The origin for the hue angle is the 
center-right of the mood plane. This hue mapping can be mirrored and rotated. A drop-off factor is applied to the 
saturation to modify the saturation curve, where a factor of 0 preserves full saturation for the whole color map. 
For reference, the following section replicates the saturated profile:
```yaml
spotify_mood_lights_sync:
  color_profile: custom
  custom_profile:
    color_mode': hs
    mirror_x: True
    mirror_y: False
    rotation: -60
    drop_off: 0
```

### Debugging color profiles

If you wish to view the color map currently in use, e.g. for debugging custom color profiles, you additionally need the
following packages. These are, however, _not_ needed for standard app operation:

```yaml
python_packages:
  - Pillow
system_packages:
  - py3-pillow
```

Adding the `color_map_image` key in the config will prompt the app to generate an image file of the used color 
map, where the x and y axes map to valence and energy, respectively. You can specify the pixel size, i.e. height and 
width, of the image and the location to which it should be saved.

```yaml
spotify_mood_lights_sync:
  color_map_image:
    size: 50
    location: /config/www/spotify-lights-sync/test.png
```

## Acknowledgments

This project is based on the following projects:

- https://github.com/ericmatte/ad-media-lights-sync
- https://github.com/tyiannak/color_your_music_mood
