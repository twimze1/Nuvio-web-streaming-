# Legacy Hornet models: F/A-18A and F/A-18B

Game-ready Blender models of the original McDonnell Douglas Hornet, built by
a script from the F/A-18A and F/A-18B general-arrangement drawings. This is
the legacy airframe, not the larger F/A-18E/F Super Hornet. Each variant has:

- weathered PBR textures (a worn fleet-service finish);
- a cockpit modelled from NASA photographs and NASA's F/A-18 cockpit layout
  drawing, with eye points for a first-person camera;
- the external stores the US Navy and Marine Corps carried on the A/B, with
  pylons, station sockets and example loadouts.

![F/A-18A](previews/FA-18A_hero.jpg)
![F/A-18A front cockpit](previews/cockpit_A_front.jpg)

## Files

| File | What it is |
| --- | --- |
| `FA-18A_Hornet.blend`, `FA-18B_Hornet.blend` | The models. Textures are in `textures/`, referenced by relative path. |
| `FA-18A_Hornet.glb`, `FA-18B_Hornet.glb` | Same aircraft for game engines, textures embedded. Includes the airframe, cockpit, pylons, station sockets and cameras, with the gear down. Loadouts are not included. |
| `FA-18A_Hornet_animated.blend`, `FA-18B_Hornet_animated.blend` | Copies of the models with the animation clips set up by `tools/setup_animations.py` (the originals are untouched); `*_animated.glb` carry the clips as glTF animations, and `*_animated_report.txt` lists what was found and set up. |
| `web/index.html` | Browser viewer: plays every animation clip on either variant, with zoom, orbit and cockpit views. One self-contained 6.8 MB file (both models gzipped, web-sized textures, all embedded) that opens straight from disk or any host. |
| `FA-18_Stores.glb` | Every store, pylon, rack and launcher. Each node sits at the origin, which is also the store's attach point. |
| `FA-18A_stations.json`, `FA-18B_stations.json` | Station manifest: socket positions, what each station carries, store data and sources, and the loadouts. |
| `textures/` | Cockpit atlas, display images, exterior atlases and the stores atlas. |
| `fa18_hornet.py` | Generator for the airframe; it builds everything else by calling the modules below. |
| `fa18_cockpit.py`, `cockpit_layout.py` | Cockpit geometry, and the panel layout it shares with the texture painter. |
| `fa18_stores.py`, `stores_data.py` | Stores, pylons, sockets and loadouts, and the weapons data they use. |
| `fa18_materials.py` | PBR materials and the exterior bake. |
| `tools/` | Texture painters, reference-line prep, overlay check, model checks, preview renders, animation set-up, browser viewer and video builders. |
| `docs/weapons_research.md`, `.json` | Research notes behind every weapon number, with sources. |

## Variants

The two variants share everything except the crew area:

- **F/A-18A:** one seat. The canopy runs 3.22–7.15 m aft of the nose tip.
- **F/A-18B:** two seats in tandem. The canopy runs 3.18–8.70 m, with a frame between the
  cockpits and a raised spine behind them. The rear cockpit has its own instrument panel,
  without a HUD (head-up display).

## Regenerating

Tested with Blender 5.3 (the `bpy` module). It should also run on Blender
4.2+, but that is untested.

```sh
cd aircraft
# 1. paint the cockpit and stores textures (Python 3 with Pillow and numpy)
python tools/make_cockpit_textures.py
python tools/make_store_textures.py
# 2. optional, slow (about 2.5 hours on 4 CPU cores): re-bake the exterior textures.
#    Panel lines come from the F/A-18B drawing, which is not stored in this repo.
#    The vectorising step needs scikit-image.
python tools/prepare_reference_lines.py PATH/TO/fa18b_sheet.gif /tmp/refs
python tools/vectorize_reference_lines.py /tmp/refs/refs.json /tmp/refs
blender -b -P fa18_hornet.py -- --variant A --bake --refs /tmp/refs/refs_hd.json --samples 4
blender -b -P fa18_hornet.py -- --variant B --bake fuselage --refs /tmp/refs/refs_hd.json --samples 4
# 3. build both variants, with GLB files and the stores library
blender -b -P fa18_hornet.py -- --variant both --glb
```

Options:

- `--variant A|B|both`
- `--out DIR`
- `--glb` (also writes `FA-18_Stores.glb`)
- `--bake [GROUP ...]`, `--refs`, `--samples`
- `--no-uv`

Without `--bake`, the build uses the textures already in `textures/`. The
wings, tail and gear atlases are shared by both variants; each variant has its
own fuselage atlas.

Rebuilds are deterministic. If you change exterior geometry, though, re-bake
that part's atlas: its automatic UV layout changes with the mesh.

## Structure and conventions

- Real-world scale in metres. The nose points along −Y, +Z is up and the port wing
  is on +X. glTF converts this on export as usual.
- One root empty per aircraft (`FA-18A_Hornet`), with its origin on the centreline at
  25 % of the mean aerodynamic chord.
- **Moving parts.** Each sits under a `<name>_Hinge` empty on its hinge line and rests
  at zero rotation; rotate it about its local X axis. Its `hinge` custom property (a
  glTF extra) records which way positive goes:

  | Part | Positive rotation |
  | --- | --- |
  | `Flap_*`, `Aileron_*`, `Stabilator_*` | trailing edge down |
  | `LEFlap_Inner_*`, `LEFlap_Outer_*` | leading edge down |
  | `Rudder_*` | trailing edge to starboard |
  | `Wing_Outer_*` | wing folds up (93° = folded: the panels stand vertical) |
  | `Canopy` | opens (front edge up, hinged at the aft end) |
  | `SpeedBrake` | opens |
  | `ArrestingHook` | hook down |

- **Collections:**
  - `Landing Gear`
  - `Cockpit`
  - `Pylons` (fitted, as usual in service)
  - `Station Sockets`
  - `Optional` (hidden): the extended refuelling probe, and `BoardingLadder_Extended`, the
    boarding ladder down to the deck, for a parked or main-menu display. The ladder is left
    out of the aircraft GLBs and exported on its own as `FA-18_BoardingLadder.glb`, in the
    aircraft's coordinates, so it lines up when placed at the same origin.
  - `Loadouts` (hidden)
  - `Stores Library` (hidden, laid out beside the aircraft)

## Cockpit

![F/A-18B rear cockpit](previews/cockpit_B_rear.jpg)

**Sources.** All are public-domain NASA photographs:

- **ARC-1993-A83-0499-34**, NASA Ames, "F/A-18 Hornet cockpit": a layout drawing of the
  front cockpit. Its scale is about 1 mm per pixel, confirmed by the 8 in DDI bezels.
  The front instrument panel is laid out in millimetres from it, in `cockpit_layout.py`.
- **ED08-0252-06**, NASA 845, an F/A-18B: the rear instrument panel. It shows the same
  displays and lower panel as the front, without the HUD.
- **ED06-0075-11:** the HUD combiner and the canopy bow.
- **EC02-0102-1, AFRC2018-0104-04, ED08-0252-26, AFRC2026-0188-01:** the SJU-5/6 seats,
  the perforated sill longerons and the canopy interior.

The photos are searchable at images.nasa.gov. NASA additions seen in them (cameras,
video panels, the large test display) were left out.

- **The NATOPS flight manual's cockpit foldouts** (see *Checked against the NATOPS
  flight manual*):
  - FO-1, the front cockpit of the A/B: side consoles, knee panels, centre pedestal,
    AOA indexer and standby compass;
  - FO-2, the rear cockpit of the B: rear instrument panel, knee panels and consoles;
  - FO-9, the SJU-5/6 seat: canopy breakers and the SAFE/ARMED handle.

**What is modelled:**

- **Main instrument panel, laid out as in the drawing:**
  - two DDIs (digital display indicators) with 20 push buttons each;
  - the up-front control panel: keypad, five option windows, scratchpad and function row;
  - the HUD control panel;
  - glareshield warning lights (FIRE, MASTER CAUTION, APU FIRE);
  - the master arm panel;
  - jettison station select and flap/gear lights;
  - the engine monitor display and fuel quantity gauge;
  - HDG/CRS knobs;
  - the horizontal situation display;
  - standby attitude, airspeed, altimeter and vertical-speed instruments, and the RWR
    (radar warning receiver) azimuth indicator.
- **Rear instrument panel of the B (FO-2):**
  - the warning and caution lights above the UFC, with the emergency jettison button to
    their left and the A/A–A/G master mode lights to their right;
  - a third DDI in the centre where the front seat has the HSD;
  - gear and flap position lights, a display select switch and a clock.
- **Knee panels and centre pedestal (FO-1, FO-2),** below the main panel:
  - front left: the landing-gear handle (wheel knob) with its DN LOCK ORIDE and WARN TONE
    SIL buttons, the launch-bar and flap switches, the select-jettison knob, the
    landing/taxi light, anti-skid and hook-bypass switches, and the emergency/parking
    brake handle;
  - front right: the brake-accumulator and HYD 1/2 pressure gauges, the caution-light
    panel, the arresting-hook handle and its light, the wing-fold handle, the FCS cool
    switch and the landing checklist;
  - front pedestal: the dispenser/ECM controls, the clock and the rudder-pedal adjust
    handle;
  - rear: the emergency landing-gear and brake handles, the ejection command selector,
    a caution panel, a HYD gauge and the cockpit altimeter; on the pedestal, the
    rudder-pedal adjust handle and the BUNO plate.
- **Side consoles (FO-1, FO-2),** panel by panel in the manual's order:
  - front left: ground power, fire test, the throttle quadrant, exterior lights, fuel,
    APU, FCS, comm, oxygen and anti-G with the LOX gauge, MC/hydraulic isolate and
    antenna select;
  - front right: electrical power with its voltmeter, ECS, interior lights, sensors,
    KY-58, two blank panels, fan test and the map case;
  - rear: the throttles, volume controls, the internal canopy-jettison handle, the
    chaff/flare programmer, oxygen and anti-G on the left; interior lights, fan test, the
    utility light and the map case on the right; the rest blank, as in the manual.
- **Glareshield coaming and HUD:** the HUD has its projector body, side posts and a tilted
  combiner.
- **Canopy bow:** three rear-view mirrors and the AIM-7 LOCK/SHOOT lights.
- **Coaming:** the AOA indexer left of the HUD (green high, amber on speed, red low) and
  the standby magnetic compass at the right end (both cockpits).
- **Ejection seats:** Martin-Baker SJU-5/A (front) and SJU-6/A (rear), with headbox,
  parachute container, side beams, gas-generator tubes, survival-kit cushion, harness,
  the yellow-and-black firing handle, the canopy breakers on the headbox and the
  SAFE/ARMED handle.
- **Controls:** the control stick, throttle quadrant with HOTAS grips, and rudder pedals.
- **Tub:** walls and a floor cut into the fuselage, the perforated canopy-sill
  longerons, and a foot well under the panel.
- **Canopy and windscreen:** separate thin transparencies (1.4 cm), so you can sit inside.

**Displays for a game.** Every screen is its own object, with 0–1 UVs and its own
material:

- `DDI_L_*`, `DDI_R_*`, `HSD_Front`, `DDI_C_Rear` (the B's centre DDI)
- `UFC_*` (scratchpad plus the five option windows)
- `HUD_Combiner_*` (alpha)

Each object has a `display` property. Swap in render textures to drive them live. The
supplied images (stores page, radar page, map, UFC readout, HUD symbology) are
representative Hornet-style formats, not recordings.

**First-person.**
- `Eye_Front` and `Eye_Rear` are empties at the design eye. Their −Z axis points
  forward and +Y up, the usual camera convention.
- Each has a child camera, `Cam_Front` or `Cam_Rear`, with an 80° field of view that
  exports to glTF.
- The front eye is 0.80 m behind the panel. The seat sits on an 18° back angle, and the
  knees clear the lower panel.
- Over the nose, the line of sight clears the front edge of the glareshield at about 7.5°
  below horizontal. The eye sits 1.34 m above the nose-tip waterline.

**Cockpit limits:**
- **Side consoles and knee panels:**
  - Panel order and contents follow the manual's foldouts. Switch spacing within each
    panel follows the drawings' arrangement and was not measured, and only the main
    legends are painted.
  - The consoles start 0.30 m behind the panel face and stand 0.16 m above the seat
    reference point, so the knee panels show over their front ends from the design eye.
  - The rear consoles' texture is half the density of the front ones (1 px/mm), as they
    are mostly blank panels.
  - Handles are fixed in their normal positions (gear down, hook up, wings spread); they
    do not move with the animation clips.
- **Legends:** panel legends were painted from the layout, not copied from the drawing,
  and are slightly larger than life so they stay legible on screen.
- **Not modelled:** the pilot.

## Textures and materials

Every material is a standard glTF metallic-roughness PBR material: base colour, an ORM
map (R occlusion, G roughness, B metallic) and an OpenGL-style normal map.

| Set | Maps | How it is made |
| --- | --- | --- |
| Exterior (`ext_fuselage_A/B`, `ext_wings`, `ext_tail`, `ext_gear`) | 8K / 8K / 4K / 4K / 2K | Procedural shader (`fa18_materials.exterior_shader`) baked in Cycles; the 8K atlases are baked as four 4K tiles |
| Cockpit (`cockpit_*`) | 4K atlas plus display images | Painted by `tools/make_cockpit_textures.py` from the shared layout |
| Stores (`stores_*`) | 4K atlas | Painted by `tools/make_store_textures.py` |

**Exterior finish:** the legacy Hornet's tactical paint scheme, worn.

- **Paint:** FS 36320 dark ghost grey on top and FS 36375 light ghost grey underneath,
  with a soft demarcation down the sides and a flatter grey radome. sRGB values are
  approximate.
- **Touch-ups:** blocky patches of fresher, mismatched paint.
- **Dirt:** grime in recesses and hinge gaps, flow streaks running aft (heavier
  underneath), and a general dirt film.
- **Wear:** chipped leading edges with bare metal showing.
- **Soot:** exhaust soot ahead of and between the nozzles, and gun-gas soot streaming aft
  from the M61 muzzle on top of the nose.
- **Panel lines:** projected from the F/A-18B drawing's top view onto upper surfaces and
  its side view onto the sides, so they follow the real airframe. The drawing has no
  underside view, so the underside only has the structural breaks.
  - The sheet resolves only about 17 mm per pixel. `tools/vectorize_reference_lines.py`
    therefore thins its lines to centre lines and traces them into polylines. It then
    redraws them as 3 mm seams at 2 mm per pixel, so up close they are crisp grooves
    rather than wide stepped bands.
  - The seams are engraved in the normal map and darkened in the colour.
- **Rivets:** flush rivet heads, 5.6 mm across (AN426, 1/8 in), in a row 12 mm either side
  of every seam at 25 mm pitch: about 34,000 traced from the drawing. Each head is a
  shallow dimple in the normal map, slightly smoother paint, and a faint grime ring.
  - They are texture, not geometry. Modelled rivets would add hundreds of thousands of
    triangles and shimmer at normal viewing distance, so games put them in the normal
    map.
  - The model itself stays at about 46,000 triangles.
- **Resolution:** the UV islands are packed tight (rotated, concave nesting). That gives
  about 1.8 mm per pixel on the 8K fuselage atlas, 1.9 mm on the tail and 2.6 mm on the
  wings, so a rivet head spans about 3 pixels. For lower settings, let the engine
  downscale (mipmaps) or resize the maps.
- **How the bake works:**
  - One Blender bake call needs several full-size float buffers, about 9 GB for an
    8192 px image. So atlases larger than 4096 px are baked as tiles: each UV is
    mapped to `uv × 2 − (i, j)`, and tile (i, j) holds exactly that quarter of the
    atlas.
  - Every pass bakes with no margin, and the image's alpha records which pixels it
    covered. The 16 px margin (nearest baked pixel) is grown once, after all passes
    and tiles. Before this, the second pass (the airframe after the closed doors)
    grew its margin over door pixels near other islands.
- **Markings:** only low-visibility national insignia, on the upper port and lower
  starboard wing. There are no unit markings, so the geometry has to read on its own.
- **Nozzles:** heat-tinted. **Gear:** dirty white.
- **Frames:** canopy frames are grey outside and flat black inside.

**Cockpit finish:**
- **Colours:** FS 36231 dark gull grey cockpit with black instrument modules and white
  legends.
- **Wear:** scuffed and chipped paint showing primer and metal at the edges, polished
  finger wear on buttons and keypad keys, boot and knee scuffs on the lower panel, and
  worn longeron tops.
- **Materials:** fabric, webbing and rubber each have their own height detail.

**Stores finish** (Navy ordnance practice, NAVEDTRA 12308):
- **Bombs:** olive-drab bodies with a rough thermal-protective coating.
- **Bands:** yellow for high explosive, brown for rocket motors, light blue for practice
  stores.
- **Missiles and other stores:** white missile bodies; grey guidance kits, tanks, pods
  and pylons.
- **Stencils:** yellow on olive drab and black on white. The nomenclature is
  representative.
- **Wear:** grime streaking aft, handling and sway-brace scuffs at the lugs, and chipped
  noses and fins.

## Weapons and stations

![Loadouts](previews/loadouts.jpg)
![Stores library](previews/stores_library.jpg)

**Station map.** Spanwise distances are from the F/A-18A/B/C/D NATOPS flight manual
(A1-F18AC-NFM-000), Fig. 4-4. The equipment per station comes from NAVEDTRA 12308,
*Aviation Ordnanceman 3 & 2* (1990, approved for public release), Fig. 14-21. That
manual is publicly posted but marked Distribution C, so check its status before citing
it in a product.

| Station | Distance from centreline | Equipment |
| --- | --- | --- |
| 1, 9 | 5.94 m | wingtip LAU-7 (always fitted) |
| 2, 8 | 3.41 m | SUU-63 pylon (BRU-32): BRU-33 twin rack, LAU-115 (+2 LAU-7), LAU-117, LAU-118 |
| 3, 7 | 2.23 m | SUU-63 pylon (BRU-32): BRU-33, LAU-117, LAU-118, 330 gal tank |
| 4, 6 | 1.13 m | LAU-116, semi-recessed (AIM-7 / AIM-120); AAS-38 pod on 4, ASQ-173 on 6 |
| 5 | 0 | SUU-62 pylon (BRU-32): BRU-33, 330 gal tank, single stores |

Fore-and-aft positions are not published. They were taken from the drawings: the pylon
noses sit about 0.35 m ahead of the wing leading edge, as in the F/A-18B top view.

**Attaching stores.**

- **Sockets:** `STA_1` … `STA_9` sit where the store's suspension point goes. Every store
  has its origin at that point (top of the body, between the lugs or rail hangers), with
  its nose along −Y.
- **Racks and launchers:** these hang their store H metres lower. The value is in
  `stores_data.EQUIPMENT` and `*_stations.json`.
- **BRU-33 CVER:** its two units sit 0.13 m either side and are canted 5° outboard.
- **Pods on 4 and 6:** these ride 2.15 m forward of the AIM-7 position, under the intake,
  ending just ahead of the main-gear bay. This is an estimate: no source gave their exact
  fore-and-aft position.
- **Example loadouts:** seven, built from loads the A/B and Desert Storm Hornets actually
  flew: `CAP`, `Fleet_air_defence`, `Strike_Mk83`, `Heavy_strike_Mk84`, `SEAD_HARM`,
  `Walleye_1991` and `Rockeye_CAS`. They are hidden collections of linked copies, and are
  also listed in the manifests.
- **Checked:** `tools/check_model.py` confirms that no store in any loadout intersects the
  airframe, the gear or another store.

**Stores modelled.** The table is generated from `stores_data.py`.

- **Era:** "baseline" means the A/B as built. "A+" means the later USMC upgrade
  (APG-73 radar, AMRAAM capability; Lot XVII C-equivalent).
- **Stations:** "not documented" means Hornets carried the store, but no source found
  gives its stations on the A/B. The manifest leaves those for you to decide.
- **Size data:** "published" means published length, diameter and span.
  "Published L/D; fins scaled" means the length and diameter are published and the fin
  planforms are scaled from photos. **Estimated** means no published dimensions were
  found (see each store's `note`).

| Id | Store | Era | Length m | Dia m | Fin span m | Carried on | A/B stations | Size data |
|---|---|---|---|---|---|---|---|---|
| AIM-9L | AIM-9L/M Sidewinder | baseline | 2.85 | 0.127 | 0.63 | LAU-7 | 1, 2, 8, 9 | published L/D; fins scaled |
| AIM-9X | AIM-9X Sidewinder | A+ | 3.02 | 0.127 | 0.45 | LAU-7 | not documented | published L/D; fins scaled |
| AIM-7M | AIM-7F/M Sparrow | baseline | 3.66 | 0.203 | 1.02 | LAU-116 (4/6), LAU-115 (2/8) | 2, 4, 6, 8 | published |
| AIM-120A | AIM-120A/B AMRAAM | A+ | 3.66 | 0.178 | 0.64 | LAU-116, LAU-115+LAU-127 | 2, 4, 6, 8 | published |
| AIM-120C | AIM-120C AMRAAM | A+ | 3.66 | 0.178 | 0.45 | LAU-116, LAU-115+LAU-127 | 2, 4, 6, 8 | published |
| AGM-65E | AGM-65E/F Maverick | baseline | 2.49 | 0.305 | 0.72 | LAU-117 | 2, 3, 7, 8 | published |
| AGM-88 | AGM-88 HARM | baseline | 4.17 | 0.254 | 1.12 | LAU-118 | 2, 3, 7, 8 | published |
| AGM-84D | AGM-84D Harpoon | baseline | 3.85 | 0.343 | 0.91 | BRU-32 | not documented | published L/D; fins scaled |
| AGM-84E | AGM-84E SLAM | A+ | 4.50 | 0.343 | 0.91 | BRU-32 | not documented | published L/D; fins scaled |
| AGM-62 | AGM-62 Walleye I ER/DL | baseline | 3.45 | 0.318 | 1.16 | BRU-32 | 2, 8 | published L/D; fins scaled |
| AGM-62II | AGM-62 Walleye II ER/DL | baseline | 4.04 | 0.457 | 1.29 | BRU-32 | not documented | published L/D; fins scaled |
| AGM-154A | AGM-154A JSOW | A+ | 4.06 | 0.340 | 0.70 | BRU-32 | not documented | published L/D; fins scaled |
| ADM-141 | ADM-141 TALD | baseline | 2.34 | 0.280 | 0.55 | TER | not documented | **estimated** section |
| GBU-12 | GBU-12 Paveway II (500 lb) | baseline | 3.33 | 0.273 | 0.30 | BRU-32 | not documented | published |
| GBU-16 | GBU-16 Paveway II (1,000 lb) | baseline | 3.68 | 0.356 | 0.38 | BRU-32 | not documented | published |
| GBU-10 | GBU-10 Paveway II (2,000 lb) | baseline | 4.32 | 0.457 | 0.48 | BRU-32 | not documented | published |
| GBU-24 | GBU-24 Paveway III | A+ | 4.39 | 0.457 | 0.91 | BRU-32 | not documented | published L/D; fins scaled |
| GBU-38 | GBU-38 JDAM (500 lb) | A+ | 2.35 | 0.273 | 0.43 | BRU-32 | not documented | published |
| GBU-32 | GBU-32 JDAM (1,000 lb) | A+ | 3.04 | 0.356 | 0.50 | BRU-32 | not documented | published |
| GBU-31 | GBU-31 JDAM (2,000 lb) | A+ | 3.88 | 0.457 | 0.64 | BRU-32 | not documented | published |
| MK-82 | Mk 82 LDGP / BLU-111 (500 lb) | baseline | 2.21 | 0.273 | 0.38 | BRU-32 or BRU-33 (two) | 2, 3, 5, 7, 8 | published L/D; fins scaled |
| MK-82SE | Mk 82 Snakeye (Mk 15 fin) | baseline | 2.17 | 0.274 | 0.40 | BRU-32 or BRU-33 | not documented | published L/D; fins scaled |
| MK-83 | Mk 83 LDGP / BLU-110 (1,000 lb) | baseline | 3.01 | 0.356 | 0.50 | BRU-32 or BRU-33 (two) | 2, 3, 5, 7, 8 | published L/D; fins scaled |
| MK-84 | Mk 84 LDGP / BLU-117 (2,000 lb) | baseline | 3.85 | 0.457 | 0.64 | BRU-32 (single only) | 2, 3, 7, 8 | published L/D; fins scaled |
| MK-20 | Mk 20 Rockeye II / CBU-59 / CBU-78 | baseline | 2.34 | 0.337 | 0.44 | BRU-32 or BRU-33 (two) | 2, 3, 5, 7, 8 | published |
| MK-77 | Mk 77 fire bomb | baseline | 3.30 | 0.530 | – | BRU-32 | 5 | **estimated** |
| LAU-61 | LAU-61 (19 x 2.75 in) | baseline | 1.52 | 0.406 | – | BRU-33 | not documented | published L/D |
| LAU-68 | LAU-68 (7 x 2.75 in) | baseline | 1.56 | 0.249 | – | BRU-33 | 2, 8 | published L/D |
| LAU-10 | LAU-10 (4 x 5 in Zuni) | baseline | 2.50 | 0.400 | – | BRU-33 | 2, 8 | **estimated** |
| B61 | B61 (shape only) | baseline | 3.60 | 0.338 | 0.57 | BRU-32 | not documented | published L/D; fins estimated |
| B57 | B57 (shape only) | baseline | 3.00 | 0.375 | 0.60 | BRU-32 | not documented | published L/D; fins estimated |
| MK-76 | Mk 76 practice bomb | baseline | 0.58 | 0.102 | 0.17 | practice rack | not documented | published L/D |
| TANK-330 | 330 US gal fuel tank (FPU-8/A) | baseline | 3.90 | 0.760 | – | BRU-32 | 3, 5, 7 | **estimated** (see note) |
| AAS-38 | AN/AAS-38 NITE Hawk FLIR pod | baseline | 1.83 | 0.330 | – | station 4 adapter | 4 | published L/D |
| LITENING | AN/AAQ-28 LITENING (USMC) | A+ | 2.20 | 0.406 | – | station 4 adapter / BRU-32 | 4, 5 | published L/D |
| ASQ-173 | AN/ASQ-173 LST/SCAM pod | baseline | 2.20 | 0.220 | – | station 6 adapter | 6 | **estimated** |
| AWW-13 | AN/AWW-13 data-link pod | baseline | 3.40 | 0.380 | – | BRU-32 | 2, 3, 5, 7, 8 | **estimated** |
| ACMI | ACMI / TACTS pod | baseline | 2.85 | 0.127 | 0.63 | LAU-7 | 1, 9 | **estimated** |

**Suspension equipment:**

| Id | Equipment | Length m | Stations | Size data |
|---|---|---|---|---|
| SUU-63 | SUU-63 wing pylon (with BRU-32) | 2.40 | 2, 3, 7, 8 | **estimated** |
| SUU-62 | SUU-62 centreline pylon (with BRU-32) | 1.90 | 5 | **estimated** |
| BRU-33 | BRU-33 VER / CVER (twin) | 1.10 | 2, 3, 5, 7, 8 | **estimated** |
| LAU-115 | LAU-115 wing missile launcher | 2.08 | 2, 8 | published length; section estimated |
| LAU-7 | LAU-7 Sidewinder rail (pylon side mount) | 1.90 | 2, 8 | **estimated** |
| LAU-117 | LAU-117 Maverick launcher | 2.39 | 2, 3, 7, 8 | published (11 × 11 in section) |
| LAU-118 | LAU-118 HARM launcher | 2.01 | 2, 3, 7, 8 | published (11.65 × 8 in section) |

**Gun.** The internal M61A1 20 mm gun holds 578 rounds (NAVEDTRA 12308). Its muzzle port
sits on top of the nose, with gun-gas vents and soot. The gun itself is internal and not
modelled.

**Not modelled:**

- **Foreign-only weapons:** ASRAAM, IRIS-T, Taurus, CRV-7, JASSM (Finland).
- **Stores with no documented A/B carriage:** mines (Mk 36/40/41, Quickstrike),
  CBU-87/89/97, SUU-25, the tow-banner adapter, the AN/ALQ-167 pod and the B43.
- **Multiple ejector racks:** MER/TER racks (other than TALD's mount) and the BRU-55,
  whose dimensions aren't published.
- **Configuration details:** guidance-kit wings are shown folded, in carriage, and
  Snakeye drag plates closed.

**Sources** (full list and disagreements in `docs/weapons_research.md`):

- NAVEDTRA 12308, *Aviation Ordnanceman 3 & 2* (1990)
- USAF *Weapons File 2003–2004*
- designation-systems.net
- FAS military analysis pages
- NWC TP 7033
- Wikipedia (and its citations)
- dstorm.eu Desert Storm loadouts (enthusiast site, medium reliability)

## Maker's markings: Julian Defense MFG

Every store, pod, tank, pylon and launcher carries Julian Defense MFG as its maker. The
markings follow US ordnance practice:

- **Bombs:** the nomenclature is stencilled in yellow, which marks high-explosive filler
  (NAVEDTRA 12308), with yellow nose bands. The lot number is stencilled at the forward
  end, followed by the maker's line. An engraved data plate sits on the body side.
- **Missiles, pods, tanks and suspension equipment:** stencilled nomenclature plus an
  engraved MIL-STD-130-style nameplate. Slim bodies carry a compact plate. The plate
  lists:
  - maker: JULIAN DEFENSE MFG
  - nomenclature
  - part number: `JDM-<store>-nnn`
  - serial number
  - lot number
- **Lot numbers:** MIL-STD-1168C layout, with maker symbol `JDM`, 2-digit year, month
  letter, 3-digit interfix and 3-digit sequence, for example `JDM88E325-021`. Baseline
  stores use 1988; A+ stores use 2004.
- **Practice stores:** marked INERT in white.
- **Not invented:** no CAGE codes, since those are real registry identifiers.
- **Changing them:** the maker name and symbol are `MAKER` and `MAKER_SYMBOL` in
  `stores_data.py`. Re-run `tools/make_store_textures.py` to repaint.

Nameplate lettering is also cut into the normal map, so it reads as engraved.

## Animations

![Animation clips](previews/animations.jpg)

Run `tools/setup_animations.py` on a model to set up its clips without changing the model.
It saves a new file, `<name>_animated.blend`:

```sh
blender -b FA-18A_Hornet.blend -P tools/setup_animations.py -- --glb
# or: open the .blend, load the script in the Text Editor, Run Script
```

**What it does:**

1. **Inspects the scene.** It finds the moving parts by name pattern and by the `hinge`
   property, then reports what it found, what it skipped and what is missing.
2. **Sets up pivots.** Hinged parts already pivot on their hinge empties. Each gear leg
   gets a new `<name>_Pivot` empty at the top of the leg, and the leg is re-parented to
   it without moving. No mesh is edited.
   - Each pivot sits under a static `<name>_Pivot_Frame` empty that holds its
     orientation, so the pivot rests at zero and only its local X rotation is keyed.
   - **Stow data:** this model's legs, drag brace and launch bar carry their stowed
     positions as `stow_*` properties. The generator works these out once, then cuts the
     wheel wells and fits the doors around exactly that motion. The script plays the
     motion as stored.
   - **Fallback search:** for a model without stow data, the script finds the motion
     itself:
     - **Nose leg:** swings forward just far enough for the wheels to sit inside the
       skin, clear of the closed doors (ray casts against the lower skin).
     - **Main legs:** swing aft while a `<name>_Twist` empty turns each post about its own
       axis. The script searches for the pose closest to "post aft, wheel flat under the
       nacelle" that keeps the leg at least 1 cm from the skin and on its own side.
       Here that gives 98.6° aft with a 33° post twist, and the wheel ends within 5.5°
       of flat.
     - **Drag brace:** folds until it is inside the skin.
   - **Doors:** close by their `travel` property, after the legs are up. On extension
     they open before the legs move.
   - **Launch bar:** folds 50° against the strut as the gear retracts, so it stows below
     the cockpit floor. Its catapult angle is the one that brings its tip 3 cm above the
     deck.
3. **Builds one Action per clip.** Blender 4.4+ slotted actions give each object its own
   slot. Keys are Bezier with clamped auto handles, eased in and out, with a fake user.
4. **Lays the clips out on the NLA.** Each object gets a track per clip, strips hold
   nothing outside their range, and the timeline has a marker per clip. The aircraft
   therefore sits in its neutral pose whenever no clip is playing.
5. **Exports a GLB** with one glTF animation per clip, each starting at time 0.

**Model changes made for the animation.** The landing gear was rebuilt from the F/A-18B
drawing's side view. Three public-domain NASA photos (listed below) settled what the
drawing doesn't show. The rest of the airframe is unchanged.

- **Nose gear:** five separate parts:
  - **Leg:** the strut and twin wheels. Its top sits 0.11 m inside the skin, so it stays
    inside when it lies forward in the bay.
  - **Launch bar:** pivoted at the front of the strut 0.27 m above the axle and resting
    about 31° nose-up, as drawn and photographed.
  - **Drag brace:** an A-frame from aft, whose arms straddle the blade antenna under the
    nose.
  - **Two pairs of bay doors**, at the drawing's positions:
    - forward pair: 3.60–4.37 m, over the stowed wheels;
    - aft pair: 4.38–5.67 m, flanking the strut.

    Both pairs hinge just outboard of the tyres and splay outward when open, by the angle
    that gives the drawing's hanging depths (0.23 m forward, 0.18 m aft).
- **Main gear:** each leg is now built as drawn:
  - a near-vertical post ahead of the wheel;
  - a trailing arm aft to the axle;
  - a diagonal shock absorber.

  Across the aircraft the legs splay outboard to the 3.11 m track, as in a head-on photo.
- **Wheel wells:** the gear goes into real bays. The fuselage is cut open under every
  door, and each bay has walls in gear-bay paint.
  - **Nose bay:** under the two pairs of doors. Its ceiling steps down under the cockpit
    floor, the stick and the seat.
  - **Drag-brace slots:** two narrow slots just aft of the nose bay, one for each arm of
    the brace. Each has a small door, and the blade antenna stays on the skin strip
    between them.
  - **Main bays:** one per nacelle, 10.00–12.00 m. The opening was traced from where the
    leg actually crosses the skin during its swing. It runs from 0.72 m out on the
    underside, round the nacelle's lower outboard corner and up the side, and it opens
    into a well inside the nacelle that holds the stowed leg.
- **Main-bay doors:** two per bay, meeting at the corner:
  - a main door hinged on the inboard edge of the underside, hanging below the nacelle
    when open, as in the drawing's side view and the head-on photo;
  - a side door hinged up the nacelle side.

  Each opening angle (65° and 50°) is the smallest that clears four things: the leg
  through its whole swing, the stowed leg while the door swings, the stores on that
  side's stations at rest (Sparrow and fuel tanks included), and the other door.
- **Bay doors:** every door is modelled closed along the skin, then hung open, so it
  closes flush into its opening. The outer skin and edges carry the airframe paint and
  the inside face the white gear-bay paint. The bake poses the doors closed and the gear
  up, so the closed doors get the panel lines, rivets and grime of the skin around them.
  The gear and doors are hidden while the rest of the airframe bakes, so they cast no
  shadows onto the skin.
- **Front foot well:** has a raised floor plate (top at 0.21 m) that roofs the nose-wheel
  bay, because the stowed tyres reach above the tub floor.
- **Pods on 4 and 6:** moved forward so they end ahead of the main bays.

`tools/check_model.py` checks the rest pose. Both gear clips were also checked at every
third frame against the whole airframe (the fuselage and its bay walls included), the
cockpit and every loadout. No part of the gear touches the skin or the bay walls. The only
contacts are:
- parts that are meant to touch: each brace and the launch bar on the strut, the stowed
  tyres under the foot-well plate, and door hinges on their edges;
- the Sparrow case listed below.

**References for the gear:**
- The F/A-18B general-arrangement drawing (side view), supplied with the project.
- NASA KSC-20170822-PH_SWW01_0215: F/A-18B nose gear, its doors, brace and launch bar.
- NASA AFRC2026-0196-027: head-on view of both main legs and the doors.
- NASA KSC-20170822-PH_SWW01_0101: underside, gear up.
- Joe Baugher's F/A-18 notes: "the main undercarriage units retract aft and rotate
  through 90 degrees so as to lie flat underneath the air intake ducts. The twin-wheel
  nose gear retracts forward."

**Browser viewer.** `web/index.html` plays the clips live in three.js. It has:
- a switch between the F/A-18A and F/A-18B;
- one row per moving system, showing its state;
- play-all, reset and speed controls (¼× to 2×);
- views from outside and from each seat's eye point;
- a zoom control with +, −, Fit and a readout. Outside it shows metres from the target;
  in a seat it shows the field of view. The scroll wheel, a pinch, and the `+`, `−` and
  `0` keys also zoom. Outside, zoom goes toward the cursor, down to 1.2 m.

Clips in different systems can run together, for example gear up with the wings folded.
The page is a single file with both models and their textures embedded, so it needs no
server: open `web/index.html` in a browser. It only needs internet access for the three.js
library and the fonts. To rebuild it after changing the models, run
`python3 tools/make_web_viewer.py`, which fills the template `tools/web_viewer.html`. The
textures are web-sized: exterior 1536 px, cockpit 2048 px and stores 1024 px. The full
4096 px maps stay in `textures/` and the GLBs.

**Video (optional).** Two tools render the same clips to an MP4. Each clip gets its own
camera with a slow eased orbit and a caption. EEVEE takes several seconds a frame without
a GPU, so a full reel is about an hour and a half on 4 CPU cores:

```sh
blender -b -P tools/render_showreel.py -- FA-18A_Hornet_animated.blend /tmp/reel 0 3 3   # workers 0, 1, 2
python3 tools/make_showreel.py /tmp/reel FA-18A_showreel.mp4                            # captions, H.264
```

**Clips** at 24 fps:

| Clip | Parts |
| --- | --- |
| `Gear_Retract`, `Gear_Extend` | gear legs (nose forward; mains aft, the posts turning so the wheels lie flat), the nose drag brace, the launch bar folding against its strut, and all bay doors: nose, drag-brace, main and side (they close after the legs are up and open first on extension) |
| `LaunchBar_Down`, `LaunchBar_Up` | nose-gear launch bar, lowered to the deck for a catapult hook-up |
| `Canopy_Open`, `Canopy_Close` | canopy, about its aft hinge |
| `Airbrake_Extend`, `Airbrake_Retract` | dorsal speed brake |
| `Controls_Roll` | ailerons and differential stabilators |
| `Controls_Pitch` | stabilators |
| `Controls_Yaw` | rudders |
| `Flaps_Down`, `Flaps_Up` | the NATOPS FULL-flap setting on deck: leading-edge flaps 12°, trailing-edge flaps 45°, ailerons drooped 42°, and both rudders toed in 30° (trailing edges inboard) |
| `WingFold_Fold`, `WingFold_Unfold` | outer wing panels, folded to vertical (93°) |
| `Hook_Down`, `Hook_Up` | arresting hook |

Deflection angles are visual, not flight-control data. Edit them in `ANGLES` at the top
of the script.

**Not animated, and why** (also in each `*_report.txt`):

- **Gear linkage:** the real legs fold and turn through linkages (retraction actuator,
  planing link, shock-strut travel) that no available source shows. Here each leg
  moves rigidly: it swings, and the main posts also turn about their own axis.
- **Main wheels:** they end within 5.5° of flat rather than exactly flat. Their axle is
  not square to the splayed post, so a single post twist cannot lay them perfectly flat.
- **Main-bay shape:** with rigid legs, a wheel that ends flat can only enter across the
  nacelle's lower outboard corner. That is why each main bay opening wraps the corner and
  needs a side door.
- **Gear against stations 4/6:**
  - With a Sparrow (AIM-7 or AIM-120) on station 4 or 6, the main bay doors and legs pass
    through the missile while they move.
  - At rest the open doors clear the missile, but the bay opening runs under the
    missile's semi-recessed body.
  - The stations' fore-and-aft position is not published. It is estimated, and on the
    real aircraft the bay and the missile do not meet.
- **Holdback fitting:** the short arm behind the nose wheel in the drawing is not
  modelled.
- **Pilot heads:** no pilot is modelled, only eye points. For the F/A-18B, the second crew
  member is missing as well. No geometry was added.

## Checked against the NATOPS flight manual

The model was compared with the F/A-18A/B/C/D NATOPS flight manual (A1-F18AC-NFM-000,
change 6, 2000). The manual is a distribution-limited document and is not stored in this
repository; only the facts used are summarised here.

**Dimensions** (manual figures are approximate):

| | Manual | Model |
| --- | --- | --- |
| Span without missiles | 37 ft 6 in (11.43 m) | 11.43 m (wing tips) |
| Span with tip missiles | 40 ft 5 in (12.32 m) | about 12.33 m (launcher axis 5.94 m plus the AIM-9 fins) |
| Span, wings folded | 27 ft 6 in (8.38 m) | 8.38 m |
| Length | 56 ft (17.07 m) | 17.07 m |
| Height to top of fins | 15 ft 3 in (4.65 m) | 4.67 m |
| Fin cant | 20° outboard | 20° |
| Height to top of closed canopy | A 10 ft 6 in (3.20 m), B 11 ft 3 in (3.43 m) | A 3.31 m, B 3.51 m (not changed, see Limits) |

**Changed to match it:**
- **Wingtip:** the structural tip now ends at the 11.43 m span. The LAU-7 tip launchers
  are separate objects (`WingtipLauncher_*`) at station 1/9, outboard of it.
- **Wing fold:** the panels fold to vertical (93° about the hinge, which allows for the
  3° anhedral). The fold hinge moved to 4.14 m from the centreline, so the folded panels
  stand 8.38 m apart.
- **Flaps clip:** uses the manual's FULL ground setting (see Clips).

**Added from it** (`fa18_exterior.py`; plain materials, outside the baked atlases):
- **Exterior lights**, each an emissive lens plus a marker empty `Light_<kind>_<where>`
  whose +Z axis points where the light shines, with custom properties `light`, `colour`,
  `rgb` and `source`, for an engine to attach a light component:
  - position lights: red (left) and green (right) at the wingtips, on the LEX forward of
    the wing root, and under the wings at the aileron hinge; white below the tip of the
    right fin;
  - eight formation strips: wingtips, the outboard faces of the fins, the aft fuselage
    below the fins, and the forward fuselage just ahead of the LEX;
  - red anti-collision strobes on the outboard faces of the fins;
  - the landing/taxi light and the three approach lights (green high AOA, amber on
    speed, red low AOA) on the nose strut, on the sides of the strut because the launch
    bar folds up against its front;
  - a marker only for the refuelling-probe light, which the manual names without placing.
- **Air-data probes:** the two pitot-static tubes under the nose, forward of the
  nosewheel well; the two angle-of-attack probes on the nose sides; the total
  temperature probe on the lower left fuselage, aft of the nosewheel.
- **Fuel vent and dump masts** at the fin tips.
- **Afterburner section:** the nozzles are now open, with a liner, a two-ring flame
  holder and a bladed turbine face behind them.
- **Boarding ladder:** a display piece only (see Collections). The manual has it stowed
  under the left LEX, so it hangs from there to the deck.

**Approximate positions:** the manual gives the side or area but not the station of the
LEX, under-wing and wingtip position lights, the formation strips, the strobes, the AOA
probes and the dump masts. These were placed where the text puts them.

**Not modelled:**
- the chaff/flare dispensers, the APU and ATS exhausts, and the ECS and heat-exchanger
  intakes (the manual does not locate them);
- the main gear's shrink and planing links (they would change the fitted retraction);
- the arresting-hook floodlight (early aircraft only);
- the ladder's drag and side braces.

## What was matched to the drawings

All views were registered to the supplied F/A-18A and F/A-18B sheets and checked by
overlaying the model's outline on each drawing (`tools/overlay_reference.py`):

- **Top view:** nose and forward fuselage, the LEX curve, wing planform and hinge lines,
  wing-fold line (model 4.14 m, drawing 4.12 m), stabilators and nozzles.
- **Side view:** nose profile, canopy profile for each variant, spine, twin fins and
  rudders, nozzle end, intake face, antennae, wheel positions, and the landing-gear
  layout (struts, braces, launch bar and bay doors).
- **Front view:** canopy height, fin cant and tip positions, fuselage and nacelle outline,
  wing height and anhedral, stabilator line, and the wingtip missile position. The front
  view shows the aircraft without its gear. The 3.11 m wheel track is the published
  figure, and the legs' outboard splay follows a NASA head-on photo.
- **Dimensions from the sheet and published specifications:**
  - length 17.07 m, wing span 11.43 m, height 4.66 m, wing area 37.16 m²
  - 5 % root and 3.5 % tip sections (NACA 65A005 / 65A003.5 mod)
  - tailplane span 6.58 m
  - wheel track 3.11 m, wheelbase 5.42 m
- **Station 1/9 at 5.94 m (NATOPS):** puts the wingtip LAU-7 launchers outboard of the
  structural tip, on adapters, as both drawings show. The span over the launchers is
  therefore 11.98 m.

## Limits

- **Canopy height:** the model's closed canopy stands about 0.1 m taller (A 3.31 m, B
  3.51 m) than the manual's approximate figures (3.20 m and 3.43 m), while the fin height
  matches. It follows the drawings. The manual alone cannot separate a shape error from
  a difference in strut compression, so it was not changed.
- **Drawing accuracy:**
  - The sheets are small line-art scans, so registration is good to about ±0.05–0.1 m.
    The sheets also disagree slightly, and published dimensions won where they
    conflicted.
  - Fuselage cross-sections are fitted to the three views; the drawings have no station
    cuts.
- **Cockpit:**
  - Front panel: exact layout from the drawing. Rear panel: exact layout from the photo.
    Consoles: generic (see above).
  - Display content is representative.
- **Textures:**
  - Panel lines on the underside are limited, because no underside drawing was used.
  - The exterior UV islands use about half of each atlas (automatic packing), so texel
    density is lower than a hand-packed layout would give.
- **Weapons:**
  - Sizes marked estimated have no published dimensions in the sources found.
  - Fore-and-aft station positions come from the drawings; the spanwise ones are
    published.
  - Leading-edge flaps do not have cut-outs for the pylon noses; drooping them far into a
    loaded pylon will clip.
- **Simplified parts:** the landing gear (rigid legs, no shock-strut travel), the intakes (short
  ducts) and the guidance-kit details.
- **Flight model:** this repository has no flight model or game code, so no flight
  behaviour was changed and no performance values were added. `*_stations.json` carries
  store masses where they are published.
