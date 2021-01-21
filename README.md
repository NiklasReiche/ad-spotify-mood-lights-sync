# Spotify Lights Sync

_AppDaemon app that synchronizes rgb lights to the mood of the currently playing spotify song in Home Assistant._

## About

This app uses the Spotify API to extract the emotional mood value of the currently playing track.
Each mood value lies on a 2D plane which is mapped to a color spectrum from which the rgb color for the light is picked. 

The default color map used by the app looks as follows. The horizontal axis ranges from negative (left) to positive (right) emotion while
the vertical axis ranges from weak (bottom) to high (top) energy. A sad, slow song is thus mapped to blue light while a happy, upbeat song
is mapped to yellow light.

<img src="https://github.com/NiklasReiche/ha-spotify-lights-sync/blob/master/examples/default_profile.png" alt="default color profile" width="200">

## Prerequisites

For this app to work, the following python packages must be installed in the AppDaemon environment:

- spotipy
- numpy

If you wish to view the color map in use for debugging color profiles, you additionally need the following python package:

- Pillow

## Installation

Download the `spotify_lights_sync` directory from inside the `apps` directory here to your local `apps` directory, then add the configuration to enable the `spotify_lights_sync` module.

## App configuration

```yaml
spotify_lights_sync:
  module: spotify_lights_sync
  class: SpotifyLightsSync
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

| key | optional | type | default | description |
|---------------------------|-------|--------|-------------|-----------------------------------------------------------|
|`module`                   | False | string |             | The module name of the app. |
|`class`                    | False | string |             | The name of the Class. |
|`client_id`                | False | string |             | The client id of the spotify developer app. |
|`client_secret`            | False | string |             | The client secret of the spotify developer app. |
|`media_player`             | False | string |             | The entity_id of the media player to sync from. Must be a spotify media player. |
|`light`                    | False | string |             | The entity_id of the light or light group to sync. |
|`color_profile`            | True  | string | `default`   | The color profile to use for mapping moods to colors. Possible values are `default`, `centered`, or `custom`. When `custom` is specified, the color map will be built from the point-color pairs provided in `custom_profile`. |
|`custom_profile`           | True  | object |             | A list of point-color pairs to use for the `custom` `color_profile`. |
|`custom_profile.point`     | False | tuple  |             | A point in the [0, 1]X[0, 1] range. |
|`custom_profile.color`     | False | tuple  |             | A rgb color value. |
|`debug`                    | True  | bool   | `false`     | Log spotify track metadata and color information for debugging. |
|`color_map_image`          | True  | object |             | Output the color map as an image for debugging. |
|`color_map_image.size`     | False | number |             | Size (height=width) of the output image in pixels. |
|`color_map_image.location` | False | string |             | Path to which the image should be saved. |

## Acknowledgments

This project is based on the following projects:
- https://github.com/ericmatte/ad-media-lights-sync
- https://github.com/tyiannak/color_your_music_mood
