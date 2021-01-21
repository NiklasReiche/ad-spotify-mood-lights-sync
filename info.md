## App configuration

```yaml
spotify_lights_sync:
  module: spotify_lights_sync
  class: SpotifyLightsSync
  client_id: !secret spotify_client_id
  client_secret: !secret spotify_client_secret
  media_player: media_player.spotify_johndoe
  light: light.bedroom
```

| key | optional | type | default | description |
|---- | -------- | ---- | ------- | ----------- |
|`module` | False | string | | The module name of the app.
|`class` | False | string | | The name of the Class.
|`hacs_sensor` | True | string | `sensor.hacs`| The entity_id of the HACS sensor.
