# Boeing P-26A "Peashooter"

An original Blender model of the real 1930s Boeing P-26A pursuit aircraft, with PBR
textures, an open cockpit and animation clips. It is separate from the F/A-18 models in
`../aircraft`, which it does not use or change.

## Files

| File | What it is |
| --- | --- |
| `P-26A_Peashooter.blend`, `.glb` | The model with baked textures. |
| `P-26A_Peashooter_animated.blend`, `.glb` | The same with the animation clips. |
| `textures/` | Two baked atlases (base colour, ORM, normal), the instrument panel and the insignia. |
| `p26a.py` | Generator: all geometry. |
| `p26a_cockpit.py` | Cockpit: panel, seat, controls, structure, eye point and camera. |
| `p26a_materials.py` | Procedural paint and weathering, painted panel and insignia, the bake. |
| `tools/animate.py` | Adds the animation clips and writes the `_animated` files. |
| `tools/render.py` | Cycles renders under a physical sky, on the wheels or in flight attitude. |

## Regenerating

Needs Blender 5.x (or the `bpy` module) with numpy and Pillow.

```sh
blender -b -P p26a.py -- --bake --glb        # build, bake the textures (about 15 min on 4 cores), export
blender -b -P p26a.py -- --glb               # rebuild using the textures already in textures/
blender -b -P tools/animate.py -- --glb      # animation clips
blender -b -P tools/render.py -- P-26A_Peashooter.blend /tmp/p26_ hero side front
```

## What it was built from

- **Shape:** the three-view of the Boeing 281 (the export P-26, the same airframe) in
  *L'Aérophile*, March 1935, which is in the public domain. Fuselage sections, the wing
  and tail planforms, the fin and rudder, the gear, the ring and the wire layout were
  measured from it. The drawing is not stored here.
- **Published dimensions** (National Museum of the US Air Force): span 27 ft 11.5 in
  (8.52 m), length 23 ft 10 in (7.26 m). The drawing was scaled to these.
- **Engine:** Pratt & Whitney R-1340 Wasp, nine cylinders, 51.75 in (1.31 m) diameter.
- **Your screenshots and cockpit video** showed the look you wanted: olive drab with the
  1941 star insignia, and the general arrangement of the cockpit. No textures or
  geometry were taken from them.

| | Published / drawing | Model |
| --- | --- | --- |
| Span | 8.52 m | 8.52 m |
| Length | 7.26 m | 7.26 m |
| Wing area | 149.5 sq ft (13.9 m²) is the usual figure | about 14.0 m² |
| Propeller | 9 ft (2.74 m); the drawing's front view gives 2.76 m | 2.74 m |
| Wheel track | 1.52 m (drawing) | 1.56 m |

## What is modelled

- **Airframe:** fuselage, the tall headrest fairing with its padded front, wire-braced
  low wing, tailplane, fin, and the three-pane windscreen.
- **Gun sight:** a long thin tube on the cowl ahead of the windscreen, tapered to a
  point at its front end, on two studs (the front one on a small block), ending at the
  glass. It follows your close-up reference picture.
- **Engine:** crankcase, nine finned cylinders with heads, rocker boxes and pushrod
  tubes, ignition ring, individual exhaust stubs, and the Townend ring.
- **Propeller:** two-blade Hamilton Standard type with the ground-adjustable hub.
- **Landing gear:** the leg fairings ("trousers") and wheel spats, wheels, and the
  faired tailwheel.
- **Bracing:** doubled front and single rear wires above and below each wing, the
  jury struts, cross and drag wires at the gear legs, all with end fittings.
- **Guns:** two Browning .30 calibre M2 aircraft guns low in the fuselage sides. Each
  has its perforated barrel jacket, receiver with top cover, belt feedway, back plate,
  buffer and charging handle, and fires through a blast tube that runs forward past the
  engine. The breech and its charging handle sit in a well in the cockpit floor beside
  the pilot's leg; the rest is hidden by the skin (`previews/p26a_guns.jpg` shows them
  with the skin hidden).
- **Muzzle markers:** `P26_Muzzle_L` and `P26_Muzzle_R` are empties at the blast tube
  mouths, for tracers and muzzle flash. The bore points along the aircraft's nose
  (−Y in Blender).
- **Details:** radio mast and aerial wires, pitot head, wingtip and tail lights.
- **Cockpit,** laid out from a photograph of a real P-26A cockpit (the museum
  aircraft):
  - a black crescent-shaped panel: airspeed, a window-type compass, tachometer and a
    small clock in the top row; altimeter, turn-and-bank, the three-in-one engine gauge
    and a fourth gauge below; a small gauge and the ignition switch at the far left;
  - a pedestal under the centre with the red fuel selector and a gauge;
  - a tall stick with a black grip, rudder pedals, the throttle quadrant on the left
    wall, a hand crank and a lever on the right wall;
  - an aluminium bucket seat with belts, frames and stringers on bare-metal walls, and
    the leather roll round the opening.
- **First person:** `P26_Eye` is an empty at the pilot's eye; its child camera `P26_Cam`
  has an 80° field of view.

About 52,000 triangles.

## Moving parts

Each rests at zero under a `<name>_Hinge` empty and turns about its local X axis. The
`hinge` custom property says which way positive goes.

| Part | Positive rotation |
| --- | --- |
| `Propeller` | turns clockwise seen from the cockpit |
| `Aileron_L`, `Aileron_R`, `Elevator_L`, `Elevator_R`, `Flap_L`, `Flap_R` | trailing edge down |
| `Rudder` | trailing edge to starboard |
| `Stick` | stick forward |

Clips (24 fps): `Prop_Spin` (one turn, loops), `Controls_Roll`, `Controls_Pitch`,
`Controls_Yaw`, `Flaps_Down`, `Flaps_Up`.

The root empty `P-26A_Peashooter` carries `ground_z`, `ground_pitch_deg` (the nose-up
angle with the tailwheel on the ground) and `main_wheel_x`. The model is built with the
fuselage level; to stand it on its wheels, pitch the root up by `ground_pitch_deg` about
the main-wheel contact point.

## Textures and materials

- **Scheme:** dark olive drab 41 over neutral gray 43, with the 1921–42 star insignia
  (white star, blue disc, red centre) in the 1941 positions: both fuselage sides, the
  upper left wing and the lower right wing. There are no unit markings or serial.
- **Weathering,** all procedural and then baked:
  - sun-faded paint on the upper surfaces;
  - round-head rivet rows along frames, stringers, ribs and spars, and panel seams;
  - chipped paint down to aluminium on leading edges, the ring lip, the port wing-root
    walkway, the cockpit rim and some rivet heads;
  - exhaust soot behind the stubs, oil streaks along the belly, grime in the seams.
- **Atlases:** `p26a_ext_*` (4096 px: airframe, ring, gear) and `p26a_parts_*` (2048 px:
  engine, propeller, guns, wires, cockpit parts). ORM is occlusion, roughness and metallic in
  the red, green and blue channels. `p26a_panel.png` is the instrument panel.
- The windscreen glass, the light lenses and the panel bezels use plain materials.

## Limits

- **Drawing:** the three-view is a small magazine drawing of the Model 281. Positions
  taken from it are good to a few centimetres. The ring is 1.41 m across so that it
  clears the engine's published diameter; the drawing shows it nearer 1.35 m.
- **Aerofoil:** the type used the Boeing 109 section. Its coordinates were not available,
  so the wing uses a 10 % cambered section of similar thickness.
- **Cockpit:** positions were read by eye from one small photograph (535 × 446 px);
  no P-26 manual was found online. Instrument faces are period-style dials drawn for
  this model, not copies of the real ones.
- **Rivets and seams** are texture, at regular spacings; they are not copied from the
  aircraft's real panel layout.
- **Guns:** the type carried two .30 calibre guns, or one .30 and one .50; this model
  has two .30s. The gun's length (about 1.0 m) and barrel length (0.61 m) are the
  published figures. No installation drawing was found, so the position in the fuselage
  and the floor wells are approximate.
- **Not modelled:** the pilot, ammunition boxes and belts, the synchroniser gear, bomb
  racks, wheel brakes and spokes.
- **Deflection angles** in the clips are for show, not the type's rigging limits.
- No flight model or performance data is included.
