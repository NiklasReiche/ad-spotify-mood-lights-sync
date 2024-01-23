from spotify_mood_lights_sync.spotify_mood_lights_sync import *
import matplotlib.pyplot as plt

def generate_subplot(profile: ColorProfile, size: int, title: str, axis) -> None:
    axis.imshow(create_color_map_image(profile, size), extent=(0, 1, 0, 1))
    axis.set_xlabel('positivity')
    axis.set_ylabel('energy')
    axis.set_title(title)


fig, (ax1, ax2) = plt.subplots(1, 2)
generate_subplot(PROFILE_DEFAULT, 250, 'Default Profile', ax1)
generate_subplot(PROFILE_SATURATED, 250, 'Saturated Profile', ax2)
fig.tight_layout()
fig.savefig('profiles.png', bbox_inches='tight')
