from spotify_mood_lights_sync.spotify_mood_lights_sync import *
import matplotlib.pyplot as plt
from PIL import Image

def generate_subplot(profile: ColorProfile, size: int, title: str, axis) -> None:
    im = Image.new('RGB', (size, size))
    im.putdata(create_color_map_image(profile, size, size))

    axis.imshow(im, extent=(0, 1, 0, 1))
    axis.set_xlabel('positivity')
    axis.set_ylabel('energy')
    axis.set_title(title)


fig, (ax1, ax2) = plt.subplots(1, 2)
generate_subplot(RGBColorProfile(PROFILE_DEFAULT), 250, 'Default Profile', ax1)
generate_subplot(HSColorProfile(PROFILE_SATURATED), 250, 'Saturated Profile', ax2)
fig.tight_layout()
fig.savefig('profiles.png', bbox_inches='tight')
