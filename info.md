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

| key                       | optional | type   | default     | description                                            |
|---------------------------|----------|--------|-------------|--------------------------------------------------------|
|`module`                   | False    | string |             | The module name of the app. |
|`class`                    | False    | string |             | The name of the Class. |
|`client_id`                | False    | string |             | The client id of the Spotify-For-Developers app to use for accessing the Spotify API. |
|`client_secret`            | False    | string |             | The client secret of the Spotify-For-Developers app to use for accessing the Spotify API. |
|`media_player`             | False    | string |             | The entity_id of the media player to sync from. Must be a spotify media player. |
|`light`                    | False    | string |             | The entity_id of the light or light group to sync. |
|`color_profile`            | True     | string | `default`   | The color profile to use for mapping moods to colors. Possible values are `default`, `centered`, or `custom`. When `custom` is specified, the color map will be built from the point-color pairs provided in `custom_profile`. |
|`custom_profile`           | True     | object |             | A list of point-color pairs to use for the `custom` `color_profile`. |
|`custom_profile.point`     | False    | tuple  |             | A point in the [0, 1]X[0, 1] range. |
|`custom_profile.color`     | False    | tuple  |             | A rgb color value. |
|`debug`                    | True     | bool   | `false`     | Log spotify track metadata and color information for debugging. |
|`color_map_image`          | True     | object |             | Output the color map as an image for debugging. |
|`color_map_image.size`     | False    | number |             | Size (height=width) of the output image in pixels. |
|`color_map_image.location` | False    | string |             | Path to which the image should be saved. |
