# Third-Party Assets

Phase 2 only includes assets released under Creative Commons CC0. The source
archives were downloaded on 2026-08-25 and normalized for the fixed Phaser
runtime contracts described below.

## Kenney Tiny Town 1.1

- Source: https://kenney.nl/assets/tiny-town
- Author: Kenney
- License: Creative Commons CC0 1.0
- Source release: 1.1 (`kenney_tiny-town.zip`)
- Modification: `Tilemap/tilemap_packed.png` was enlarged from 16×16 tiles to
  32×32 tiles with nearest-neighbor sampling. No smoothing or repainting was
  applied. The normalized tileset was used to assemble the single outdoor Tiled
  JSON map.
- Repository paths:
  - `frontend/public/assets/phase2/tiles/tiny-town-32.png`
  - `frontend/public/assets/phase2/maps/town.json`

## Eldiran 32×32 RPG Character Sprites

- Source: https://opengameart.org/content/32x32-rpg-character-sprites
- Author: Eldiran
- License: Creative Commons CC0 1.0
- Source release: `RPGCharacterSprites32x32.png`, published 2015-10-14
- Modification: the source image's opaque magenta color key was converted to a
  transparent alpha channel, then selected CC0 character rows were cropped into
  a common 9-frame contract: three down frames, three side frames, and three up
  frames. The NPC sheet contains one idle frame each for Ryan, Shir, and Grey.
  No frames from other projects were added.
- Repository paths:
  - `frontend/public/assets/phase2/sprites/adventurer-mage.png`
  - `frontend/public/assets/phase2/sprites/adventurer-ranger.png`
  - `frontend/public/assets/phase2/sprites/adventurer-cleric.png`
  - `frontend/public/assets/phase2/sprites/npcs.png`

## Kenney Interface Sounds 1.0

- Source: https://kenney.nl/assets/interface-sounds
- Author: Kenney
- License: Creative Commons CC0 1.0
- Source release: 1.0 (`kenney_interface-sounds.zip`)
- Modification: `Audio/click_004.ogg` was copied without transcoding and renamed
  for its story-page use.
- Repository path:
  - `frontend/public/assets/phase2/audio/page-turn.ogg`

## Reference repositories

The two repositories under `D:\pythonproject\素材` were used only for
architecture and interaction reference. No image, audio, map, or other binary
asset was copied from either repository.
