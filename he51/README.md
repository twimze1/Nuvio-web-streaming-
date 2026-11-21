# Heinkel He 51 A-1

An original Blender model of the real 1930s Heinkel He 51 A-1 biplane fighter, with PBR
textures, an open cockpit and animation clips. It is a separate model: it does not use
or change the F/A-18 files in `../aircraft`. It shares its mesh builder, bake and render
tool with the P-26A in `../p26a`, so that folder must stay beside this one to regenerate.

## Files

| File | What it is |
| --- | --- |
| `He-51A-1.blend`, `.glb` | The model with baked textures. |
| `He-51A-1_animated.blend`, `.glb` | The same with the animation clips. |
| `textures/` | Two baked atlases (base colour, ORM, normal), the instrument panel and the cross decal. |
| `he51.py` | Generator: all geometry. |
| `he51_cockpit.py` | Cockpit: panel, padding, seat, controls, structure, eye point and camera. |
| `he51_materials.py` | Procedural paint, markings and weathering, painted panel, the bake. |
| `tools/animate.py` | Adds the animation clips and writes the `_animated` files. |
| `previews/` | Renders of the finished model. |

## Regenerating

Needs Blender 5.x (or the `bpy` module) with numpy and Pillow.

```sh
blender -b -P he51.py -- --bake --glb        # build, bake the textures (about 15 min on 4 cores), export
blender -b -P he51.py -- --glb               # rebuild using the textures already in textures/
blender -b -P tools/animate.py -- --glb      # animation clips
blender -b -P ../p26a/tools/render.py -- He-51A-1.blend /tmp/he51_ --scale 1.3 --exposure -0.6 hero side front
```

## What it was built from

- **Published dimensions:** span 11.0 m, length 8.4 m, height 3.2 m, wing area 27.2 m².
- **Shape:** no public three-view drawing was found. The fuselage profile, the fin and
  rudder, the wing positions and chords, the gear and the tail skid were measured from a
  side-on picture of an He 51 A-1 of JG 132 on Wikimedia Commons, scaled to the published
  length. Spans, strut positions and the tailplane outline came from your top and front
  screenshots. The pictures are not stored here.
- **Your screenshots** showed the look you wanted: the pale grey scheme and markings, the
  nose, exhausts and radiator, and the cockpit layout. No textures or geometry were taken
  from them.

| | Published | Model |
| --- | --- | --- |
| Span | 11.0 m | 11.00 m |
| Length | 8.4 m | 8.38 m |
| Height, tail down | 3.2 m | 3.23 m (top of the upper wing) |
| Wing area | 27.2 m² | about 27.1 m² |

## What is modelled

- **Airframe:** fuselage with the boxy metal nose and rounded nose bowl, upper wing with
  the centre-section cut-out, shorter lower wing set further aft, tailplane, fin.
- **Engine bay:** a recessed exhaust trough on each side of the nose with six upright
  stubs, gun troughs along the top of the cowl, and the radiator with shutter slats
  under the fuselage between the gear legs. The engine itself is hidden by the cowling,
  as on the aircraft.
- **Propeller:** two-blade wooden propeller, small spinner and the wrapped hub.
- **Struts and wires:** N-shaped cabane and interplane struts, flying and landing wires,
  cross bracing between the gear legs, tail bracing wires, all with end fittings.
- **Landing gear:** faired cantilever legs, wheel spats, wheels, and the tail skid.
- **Details:** small frameless curved windscreen on a black base strip, ring-and-bead
  gun sight and its mount, aerial mast, foot step under the port wing root.
- **Cockpit,** laid out from your cockpit screenshots:
  - a grey upper panel with the Bosch magneto switch, altimeter (Höhe), airspeed
    (Fahrt), turn-and-bank (Dreht / Hängt), tachometer and a small clock;
  - a lower panel with five small engine gauges, the compass, a red switch box, an
    orange push button and label plates;
  - the two red-knobbed gun charging handles left of centre;
  - a brown padded roll above the panel and tan leather round the opening;
  - a stick with a ring grip, rudder pedals, the throttle on the left wall and two
    yellow-knobbed levers on the right wall;
  - a seat with belts, and the welded steel-tube structure on the walls.
- **First person:** `He51_Eye` is an empty at the pilot's eye; its child camera
  `He51_Cam` has an 80° field of view.

About 22,000 triangles.

## Moving parts

Each rests at zero under a `<name>_Hinge` empty and turns about its local X axis. The
`hinge` custom property says which way positive goes.

| Part | Positive rotation |
| --- | --- |
| `Propeller` | turns clockwise seen from the cockpit |
| `Aileron_L`, `Aileron_R` (upper wing only), `Elevator_L`, `Elevator_R` | trailing edge down |
| `Rudder` | trailing edge to starboard |
| `Stick` | stick forward |

Clips (24 fps): `Prop_Spin` (one turn, loops), `Controls_Roll`, `Controls_Pitch` (with
the stick), `Controls_Yaw`. The He 51 has no flaps.

The root empty `He-51A-1` carries `ground_z`, `ground_pitch_deg` (the nose-up angle with
the tail skid on the ground) and `main_wheel_x`. The model is built with the fuselage
level; to stand it on its wheels, pitch the root up by `ground_pitch_deg` about the
main-wheel contact point.

## Textures and materials

- **Scheme:** overall light grey (RLM 63), black crosses with white edging on both
  fuselage sides, on top of the upper wing and under the lower wing, two narrow black
  bands round the rear fuselage, black-white-red stripes across the starboard side of
  the fin and rudder, and a red band with a white disc on the port side.
- **The white disc is blank.** The swastika carried there in 1935–36 is not drawn.
- **Fabric and metal:** the wings, tail and rear fuselage show rib tapes and stringers
  under the fabric, with the plywood leading edges left smooth; the metal nose shows
  panel seams and fasteners.
- **Weathering,** all procedural and then baked: exhaust soot behind the stubs, oil
  along the belly, dirt beside the rib tapes and in the seams, chipped paint down to
  aluminium on the nose panels.
- **Atlases:** `he51_ext_*` (4096 px: airframe, gear, radiator) and `he51_parts_*`
  (2048 px: propeller, exhausts, struts, wires, cockpit parts). ORM is occlusion,
  roughness and metallic in the red, green and blue channels. `he51_panel.png` is the
  instrument panel; `balkenkreuz.png` is the cross decal used by the bake.
- The windscreen glass and the instrument rims use plain materials.

## Limits

- **No drawing:** the shape comes from one side-on picture and screenshots, not from a
  dimensioned three-view. Lengths and heights match the published figures; cross-sections
  and the plan view are good to a few centimetres at best.
- **Propeller diameter** (3.1 m) is an estimate from photographs.
- **Aerofoil:** the real section was not available; the wings use an 11 % cambered
  section.
- **Cockpit:** positions were read by eye from your screenshots. Instrument faces are
  period-style dials drawn for this model, not copies of the real ones.
- **Rib, stringer and panel lines** are texture, at regular spacings; they are not copied
  from the aircraft's real structure.
- **Not modelled:** the pilot, the engine under the cowling, the guns themselves (only
  their troughs), the rear-view mirror, lights, control cables and horns, wheel brakes.
- **Deflection angles** in the clips are for show, not the type's rigging limits.
- No flight model or performance data is included.
