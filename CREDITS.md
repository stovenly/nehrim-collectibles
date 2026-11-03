# Credits

## The game

[Nehrim: At Fate's Edge](https://sureai.net/) is © SureAI. All rights to the game and its
content belong to SureAI, including everything here taken from it:

- the collectible placements, read out of `Nehrim.esm`
- the item icons, the Nehrim mark, and the leather, parchment and rule textures, taken from the game's archives
- the Arktwend world map, taken from the game's archives
- the local map images in `docs/img/local`, rendered from the game's world data, meshes and textures, including its map paper

This is a fan project and is not affiliated with or endorsed by SureAI or Bethesda Softworks.

## Local maps

`tools/localmap.py` reproduces the look of the local maps drawn by the Oblivion engine, © Bethesda Softworks.
Its camera, render passes and ink and paper shading were worked out by disassembling `Oblivion.exe` and the
game's compiled shaders. It contains none of the game's code, shaders or assets, and reads the assets from a
local install when it runs. It differs from the game in leaving out trees and the panels that hide secret rooms,
and in fitting each interior to the image.

## Map

| Work | Author | Used for |
|---|---|---|
| [Nehrim map](https://map.nehrim.sureai.net/) | SureAI | The Nehrim world map tiles, and the projection pins are placed with |

## Location notes

From the [Nehrim Wiki](https://nehrim.fandom.com), under
[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/):

- [Magic Symbols](https://nehrim.fandom.com/wiki/Magic_Symbols)
- [Unique plants](https://nehrim.fandom.com/wiki/Unique_plants)
- [The Books of Conjuration](https://nehrim.fandom.com/wiki/Almanac_of_Conjuration)
- [Potions](https://nehrim.fandom.com/wiki/Potions)

## Save file format

The save reader follows UESP's documentation of the Oblivion save format, under
[CC BY-SA 2.5](https://creativecommons.org/licenses/by-sa/2.5/):

- [Save File Format](https://en.uesp.net/wiki/Oblivion_Mod:Save_File_Format)
- [REFR change records](https://en.uesp.net/wiki/Oblivion_Mod:Save_File_Format/REFR)
- [ACHR and ACRE change records](https://en.uesp.net/wiki/Oblivion_Mod:Save_File_Format/ACHR)
- [Inventory](https://en.uesp.net/wiki/Oblivion_Mod:Save_File_Format/Inventory)
- [Properties](https://en.uesp.net/wiki/Oblivion_Mod:Save_File_Format/Properties)

## Typefaces

All under the [SIL Open Font License 1.1](https://openfontlicense.org).

| Face | Copyright |
|---|---|
| IM Fell English, IM Fell English SC | Igino Marini ([iginomarini.com](https://iginomarini.com/fell/the-revival-fonts/)), served by [Google Fonts](https://fonts.google.com/specimen/IM+Fell+English) |
| OpenDyslexic | Abbie Gonzalez ([opendyslexic.org](https://opendyslexic.org)) |

## Tools

| Work | Author | Used for |
|---|---|---|
| [Pillow](https://python-pillow.github.io) | Jeffrey A. Clark and contributors | Converting game textures and map tiles |
| [The Elder Scrolls Construction Set](https://en.uesp.net/wiki/Oblivion_Mod:Construction_Set) | Bethesda Softworks | Inspecting cells while placing collectibles |
| [PyFFI](https://github.com/niftools/pyffi) | NifTools developers | Reading the game's meshes for the local maps |
| [ModernGL](https://github.com/moderngl/moderngl) | Szabolcs Dombi | Rendering the local maps |
| [NumPy](https://numpy.org) | NumPy developers | Geometry and shading for the local maps |
