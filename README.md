# Spotify Mood Lights Sync

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs) [![GitHub Workflow Status](https://img.shields.io/github/workflow/status/NiklasReiche/ad-spotify-mood-lights-sync/Validate?style=for-the-badge)](https://github.com/NiklasReiche/ad-spotify-mood-lights-sync/actions)

_AppDaemon app that synchronizes rgb lights to the mood of the currently playing spotify song in Home Assistant._

## About

This app uses the Spotify API to extract the emotional mood value of the currently playing track. Each mood value lies on a 2D plane which is mapped to a color spectrum from which the rgb color for the light is picked.

The default color map used by the app looks as follows. The horizontal axis ranges from negative (left) to positive (right) emotion while the vertical axis ranges from weak (bottom) to high (top) energy. A sad, slow song is thus mapped to blue light while a happy, upbeat song is mapped to yellow light.

<img src="https://github.com/NiklasReiche/ha-spotify-lights-sync/blob/master/examples/default_profile.png" alt="default color profile" width="200">

## Prerequisites

For this app to work, the following python packages must be installed in the AppDaemon environment:

- spotipy
- numpy

If you wish to view the color map currently in use for debugging color profiles, you additionally need the following python package:

- Pillow

You may need to also specify the following system packages depending on your system setup:

```yaml
system_packages:
  - jpeg
  - tiff
```

## Issues

Since the Spotify integration in Home Assistant only polls the Spotify API every 30 seconds or so to detect when the currently playing song changes, the light synchronization may be delayed by up to 30 seconds in the worst case.

## Installation

Use [HACS](https://hacs.xyz/) or download the `spotify_mood_lights_sync` directory from inside the `apps` directory here to your local `apps` directory, then add the configuration to enable the `spotify_mood_lights_sync` module.

#### Minimal configuration:

```yaml
spotify_mood_lights_sync:
  module: spotify_mood_lights_sync
  class: SpotifyMoodLightsSync
  client_id: !secret spotify_client_id
  client_secret: !secret spotify_client_secret
  media_player: media_player.spotify_johndoe
  light: light.bedroom
```

## App configuration

```yaml
spotify_mood_lights_sync:
  module: spotify_mood_lights_sync
  class: SpotifyMoodLightsSync
  client_id: !secret spotify_client_id
  client_secret: !secret spotify_client_secret
  media_player: media_player.spotify_johndoe
  light: light.bedroom
  color_profile: default
  custom_profile:
    - point: [0, 0]
      color: [0, 0, 255]
    - point: [1, 0]
      color: [0, 255, 0]
    - point: [0, 1]
      color: [255, 0, 0]
    - point: [1, 1]
      color: [255, 255, 0]
  debug: false
  color_map_image:
    size: 50
    location: /home/homeassistant/.homeassistant/www/spotify-lights-sync/test.png
```

| key                        | optional | type   | default   | description                                                                                                                                                                                                                    |
| -------------------------- | -------- | ------ | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `module`                   | False    | string |           | The module name of the app.                                                                                                                                                                                                    |
| `class`                    | False    | string |           | The name of the Class.                                                                                                                                                                                                         |
| `client_id`                | False    | string |           | The client id of the Spotify-For-Developers app to use for accessing the Spotify API.                                                                                                                                          |
| `client_secret`            | False    | string |           | The client secret of the Spotify-For-Developers app to use for accessing the Spotify API.                                                                                                                                      |
| `media_player`             | False    | string |           | The entity_id of the media player to sync from. Must be a spotify media player.                                                                                                                                                |
| `light`                    | False    | string |           | The entity_id of the light or light group to sync.                                                                                                                                                                             |
| `color_profile`            | True     | string | `default` | The color profile to use for mapping moods to colors. Possible values are `default`, `centered`, or `custom`. When `custom` is specified, the color map will be built from the point-color pairs provided in `custom_profile`. |
| `custom_profile`           | True     | object |           | A list of point-color pairs to use for the `custom` `color_profile`.                                                                                                                                                           |
| `custom_profile.point`     | False    | tuple  |           | A point in the [0, 1]X[0, 1] range.                                                                                                                                                                                            |
| `custom_profile.color`     | False    | tuple  |           | A rgb color value.                                                                                                                                                                                                             |
| `debug`                    | True     | bool   | `false`   | Log spotify track metadata and color information for debugging.                                                                                                                                                                |
| `color_map_image`          | True     | object |           | Output the color map as an image for debugging.                                                                                                                                                                                |
| `color_map_image.size`     | False    | number |           | Size (height=width) of the output image in pixels.                                                                                                                                                                             |
| `color_map_image.location` | False    | string |           | Path to which the image should be saved.                                                                                                                                                                                       |

### Conditional execution

You can switch the light synchronization on and off through Home Assistant by using AppDaemon [Callback Constraints](https://appdaemon.readthedocs.io/en/latest/APPGUIDE.html#hass-plugin-constraints).
For example, you can control the execution with an `input_boolean` switch:

```yaml
spotify_lights_sync:
  ...
  constrain_input_boolean: input_boolean.spotify_lights_sync_toggle
  ...
```

### Custom color profile

You can create your own color profile for the app to use by specifying the `custom_profile` app argument and setting `color_profile` to `custom`.
In order to create a color map the app expects a list of points on the 2D plane with a corresponding rgb color for each point. The color value for a song can then be interpolated from the given colors based on where the mood value of that song lies on the 2D plane.
The mood of a song is a 2-dimensional value in the range [0.0,1.0]x[0.0,1.0] where the first axis is the valence, and the second axis the energy of the song. See the [Spotify API](https://developer.spotify.com/documentation/web-api/reference/#object-audiofeaturesobject) for more information on these values.

## Acknowledgments

This project is based on the following projects:

- https://github.com/ericmatte/ad-media-lights-sync
- https://github.com/tyiannak/color_your_music_mood
