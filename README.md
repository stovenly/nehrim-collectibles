# Nehrim Collectibles Tracker

A static web page that reads a Nehrim save (`.ess`) in the browser and lists, on a list and on the world map, what the player has not collected yet:

- Magic Symbols (100)
- Sparks of Fire Caps (84 plants, 4 loose ingredients, 1 on the Dwarven Thief's corpse)
- Ice Claws (153 plants, 3 loose ingredients, 2 in the Stoneworld hard reward barrel)
- Almanacs of Conjuration (21 placed, 1 carried by the Keeper of the Last Barrier)
- Potions of Encumbrance (27)

Nothing is uploaded: the save is parsed client-side by `docs/js/ess.js`.

## How it works

Symbols and plants run a script that calls `Disable` on the reference; picked-up items are removed from the world. The save stores both as a REFR change record whose form flags have the disabled (`0x800`) or deleted (`0x20`) bit set.

Copies in a corpse or container are found when that reference's inventory change record shows the item's count reduced.

Symbols also bump the global `NehrimSymbolVar`; the page cross-checks it against the disabled count and warns if they disagree.

The collectible list is generated from the game data, not hand-written:

- every placed reference of `NehrimSymbol` (ACTI), `UNIPerFeuerfunke` and `UNIPerEispranke` (FLOR) in `Nehrim.esm`, minus the six in the developer test cell `GameplayNewObjects`
- IDs (`MS001`, `FS01`, `IC001`, …) from the *Magic Symbol / Fire Sparks / Ice Claws Collection* plugins on Nexus
- English names from `Translation.esp`
- indoor collectibles are pinned at the overworld door reached by following load doors outward
- Magic Symbol location notes from the [Nehrim Wiki](https://nehrim.fandom.com/wiki/Magic_Symbols) (CC BY-SA), matched by hand in `tools/symbol_wiki_map.json`

## Layout

- `docs/` — the site (GitHub Pages serves this folder)
- `tools/` — data extraction (`build_data.py`, `tes4.py`, `bsa.py`) and checks (`check-saves.js`, `screenshot.js`)
- `research/` — source material the build reads or that was used to work out the formats

## Rebuilding the data

Needs a Nehrim install with the three Collection plugins in `Data/` (they don't need to be active).

```sh
python -m venv tools/.venv
tools/.venv/Scripts/pip install pillow
tools/.venv/Scripts/python tools/build_data.py
tools/.venv/Scripts/python tools/build_assets.py   # icons and menu textures into docs/img
npm test                      # parses every save in the game's Saves folder
node tools/screenshot.js <save.ess>   # renders the page headless into research/shots/
```

## Publishing

Repository settings → Pages → Deploy from a branch → `main`, folder `/docs`.

## Caveats

Results assume an unmodded Nehrim. Mods that move, add or remove symbols or plants can make them wrong.
