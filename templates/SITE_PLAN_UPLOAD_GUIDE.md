<!-- Sufi -->

# Site plan upload guide

When you start at a new construction site, upload a picture of its layout. The AI reads it and the dashboard draws it as a
2D pin board. Incidents logged at a place on the plan are pinned there.

## What to upload

1. **One top-down plan** (looking straight down) as `.png`, `.jpg`, `.jpeg` or `.webp`. Large images are shrunk in the browser.
2. **Cropped to the site boundary.** Cut off the title block, the legend, the notes and any margin.
3. **The real width of the picture in metres.** Measure it from a dimension or the scale bar. This is the only number you
   must type. The depth is worked out from the picture's shape.
4. **A name on every structure and area**, for example `Block A`, `Site office`, `Basement B2`.

The app is not tied to one site: every site uploads its own plan. These sample layouts are in `templates/` to try the
feature, or to copy the style when you draw your own. Type the width shown as the real width of the picture.

| File | Site | Width to type |
|---|---|---|
| `sample_site_plan.png` | Tower block site (two blocks, basement, crane) | 90 m |
| `sample_warehouse_complex_120m.png` | Warehouse and logistics complex | 120 m |
| `sample_city_tower_60m.png` | City-centre tower with a podium, a tight site | 60 m |
| `sample_school_extension_100m.png` | School extension next to an occupied school | 100 m |
| `sample_house_renovation_45m.png` | House extension and renovation, a small plot | 45 m |

## What the AI looks for

| Type | What to draw on the plan |
|---|---|
| `building` | A large labelled rectangle |
| `tower_crane` | A small box, with a dashed circle for the swing radius |
| `excavation` | A hatched rectangle labelled basement, pit or B2 |
| `scaffold` | A dashed outline along a building facade |
| `cabin` | Site office, welfare, canteen or dormitory cabins |
| `laydown` | Storage and stockpile areas |
| `gate` | The entrance on the boundary |
| `road` | Haul roads and access routes |
| `power` | Switchroom, generators, transformers |
| `zone` | Any other labelled area (loading bay, parking, assembly point) |

## Check what the AI read

You land on a review screen that shows the plan as a map. No numbers to type:

- **Click an area** to select it, then rename it, change what it is, add "Also called" names, or delete it.
- **Drag an area** to move it, and **drag a corner** to resize it.
- **Add area** puts a new box in the middle of the map for you to place.

Nothing is stored until you press **Save**. The crane's swing circle is a default 30 m radius.

## Pinning incidents

An incident is pinned on the area whose name, or one of its "other names", matches the incident's location text. For example,
add `Scaffold` as an other name of `Block B scaffold`. Locations that match no area are listed under **Not on the plan**.
