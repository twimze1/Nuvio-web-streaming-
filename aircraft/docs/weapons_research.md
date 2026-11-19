# Legacy F/A-18A/B Hornet: external stores research notes

Research notes behind `stores_data.py`. Companion to `weapons_research.json` (69 entries). All dimensions in the JSON are metric, with the original imperial figures in each entry's `notes`. The modelled subset and the geometry choices are in `../stores_data.py` and the README's Weapons section.

## 1. Key sources and caveats

| Source | What it gave | Status |
|---|---|---|
| **NAVEDTRA 12308 *Aviation Ordnanceman 3 & 2*, June 1990** (bulletpicker.com PDF) | **Fig 14-21, the F/A-18 station-equipment chart** (the main station source); gun data (578 rds, muzzle); BRU-32/33, LAU-7/115/116/117/118 descriptions; Mk 80 table; Mk 20/CBU-59; Mk 77; colour codes | **Distribution A**: approved for public release. Primary Navy source. |
| **A1-F18AC-NFM-000 NATOPS Flight Manual, F/A-18A/B/C/D, 15 Sep 2008** (vmfa251.org PDF) | **Fig 4-4: station spanwise distances**, fuel-tank stations/weights, asymmetry limits, gross weights, 400/570-round gun loads, pod side (LDT/SCAM/NAVFLIR right) | **Distribution Statement C** (US Govt and contractors only), though it is posted publicly on a squadron association site. I used it for facts that are not sensitive. Decide yourself whether to cite it. |
| USAF *Weapons File 2003-2004* (Eglin AAC/APD) | Dimensions and weights for missiles, bombs, LGBs, JDAM, launchers and B61 | Authoritative for the USAF; Navy variants sometimes differ. |
| NWC TP 7033 (Naval Weapons Center, 1989) | CBU-78/B Gator (Mk 7-type dispenser) dimensions and fin spans | Primary. Used for the whole Mk 7 dispenser family (Mk 20, CBU-59, CBU-78). |
| designation-systems.net (A. Parsch) | Missile, Paveway and JDAM tables; equipment designations | Good secondary source. |
| FAS man.fas.org | Launcher and rack descriptions, SLAM-ER station clearance, AAS-38/ASQ-173 stations, gun | Secondary; partly Navy NTSP-derived. |
| dstorm.eu F/A-18 loadout page | Desert Storm USN/USMC Hornet loads by station | Enthusiast site, credited to a USMC retiree. Medium reliability. The table is laid out from station 9 to station 1. |

Sites I could not reach from this environment: globalsecurity.org (403), tpub.com/navyaviation.tpub.com (connection reset), web.archive.org, navy.mil fact file (403), airvectors.net, marines.mil PDF. Facts attributed to the USMC *Concepts & Programs 2010* document and to the 1999 McCorkle testimony come **only from search-engine snippets**. I did not open those documents.

## 2. Station map (F/A-18A/B; numbered 1 to 9 from left wingtip to right wingtip)

The spanwise distances come from NATOPS Fig 4-4, "Distance from aircraft centerline": **1/9 = 19.5 ft (5.94 m), 2/8 = 11.2 ft (3.41 m), 3/7 = 7.3 ft (2.23 m), 4/6 = 3.7 ft (1.13 m), 5 = 0.** These are the store-station lateral positions. I found no public butt-line (BL) or fuselage-station (FS, longitudinal) figures, so **longitudinal positions are unverified**. Use photos or 3-views for those. As a cross-check, NATOPS gives span 37 ft 6 in without missiles and 40 ft 5 in with tip missiles. The tip missile at 19.5 ft therefore sits about 0.75 ft outboard of the wingtip, which is consistent.

AO 3&2 (1990) Fig 14-21 shows which equipment goes on which station:

| Equipment | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| LAU-7/A (wingtip AIM-9 rail) | X | | | | | | | | X |
| SUU-63/A wing pylon (contains BRU-32/A) | | X | X | | | | X | X | |
| SUU-62/A centreline pylon (contains BRU-32/A) | | | | | X | | | | |
| BRU-32/A rack / BRU-33/A VER | | X | X | | X | | X | X | |
| LAU-117/A (Maverick), LAU-118/A (HARM) | | X | X | | | | X | X | |
| LAU-115/A (AIM-7), alone or with 2x LAU-7/A | | X | | | | | | X | |
| LAU-116/A (semi-recessed AIM-7) + latch assembly | | | | X | | X | | | |
| Fuel tank 315/330 gal (NATOPS) | | | X | | X | | X | | |
| AN/AAS-38 FLIR or LITENING (USMC) | | | | X (port) | (LITENING also on 5) | | | | |
| AN/ASQ-173 LST/SCAM (AAR-50 NAVFLIR is C/D only) | | | | | | X (stbd) | | | |

Modelling details:
- The **wingtip LAU-7s are always fitted**. NATOPS lists flight without the LAU-7A tip rails among its prohibited items.
- The **BRU-33A/A CVER cants its two ejector units 5° outboard** (FAS). Each unit carries one store of up to 1,000 lb, so the rack does not take Mk 84s.
- The **LAU-116 sits inside fuselage cavities**, so the AIM-7 or AIM-120 rides semi-recessed. The cavity is left and right handed.
- **Station-4 pods are port-side items.** USMC LITENING for station 4 was a "left-handed" pod with its own mounting pylon.
- Pylon variants changed between production blocks. Early A/B (BuNo 161353-163175) used SUU-63/A and SUU-62/A; later aircraft used A/A and C/A versions. This split comes from kit-vendor listings plus dstorm.eu, so confidence is low.

## 3. External load limits

- **Total external load.** The usual figure is **13,700 lb (6,214 kg)** of "external fuel and ordnance" (Wikipedia, citing the Navy fact file and NATOPS). FAS gives the same figure as external ordnance for the **C/D**. FAS's Jane's-style weight table instead gives **"maximum external stores load 7,031 kg" (≈15,500 lb)**. **The sources disagree**, and I found no number specific to the A/B.
- **Maximum takeoff and catapult gross weight:** 51,900 lb (23,541 kg). Basic aircraft is 24,000-25,000 lb (NATOPS 2008).
- **Per-station weight limits are unverified.** The only figure found is a blog footnote (navalgazing.net) saying "all four [wing] stations on the Legacy Hornet are rated to 2,600 lb". Confidence is low. The BRU-33 VER is limited to 2 × 1,000 lb (AO 1990/FAS).
- **Lateral asymmetry (NATOPS):** 26,000 ft-lb in flight and 22,000 ft-lb for field takeoff. Catapult launches are limited to 6,000 ft-lb at a weight board of 36,000 lb or less, and 22,000 ft-lb at 37,000 lb or more. Carrier landings are limited to 17,000 or 14,500 ft-lb depending on weight. NATOPS warns that releasing a store over 2,320 lb from station 2 or 8 can exceed the limit.
- **Fuel tanks:** stations 3/5/7 only. Carriage limit is 1.6 IMN. Carrier landing with more than 500 lb in the centreline tank is prohibited. Single-seat aircraft with a centreline tank only are limited to 1.8 Mach.

## 4. Typical A/B loads

The station-by-station loads below are from dstorm.eu (Desert Storm USN/USMC, mixed A/C/D). Mission descriptions also draw on Wikipedia and the AO chart.

- **Fleet air defence / CAP:**
  - Basic fit: AIM-9L/M on 1/9, AIM-7M on 4/6, 330-gal tanks on 3/5/7.
  - Heavier fit: AIM-7M also on 2/8 (LAU-115). That gives 4× AIM-7 + 2× AIM-9 + 3 tanks.
  - Alternative: twin AIM-9 on LAU-115 + 2× LAU-7 at 2/8.
  - A+ era: AIM-120 replaces AIM-7 on the same stations. The VX-4 photo of 10 AMRAAM + 2 AIM-9 was a test configuration.
- **Strike:**
  - AIM-9 on 1/9.
  - AIM-7 or pods on 4/6. Pods are AAS-38 on 4 and ASQ-173 on 6.
  - Tanks on 3/7 (sometimes on 5).
  - BRU-33 VERs on 2/8 carrying 2× Mk 82, Mk 83 or Mk 20 each.
  - Centreline: tank, or a single Mk 82, Mk 83, Mk 20 or Mk 77.
  - Without tanks: 4× Mk 83 single on 2/3/7/8, or VERs on all four wing stations.
- **Heavy strike:** 4× Mk 84 on 2/3/7/8. Saratoga's Hornets did this on day 1 of Desert Storm; those aircraft were F/A-18Cs.
- **SEAD:** 2-4× AGM-88 on 2/8 (+3/7), AIM-7 on 4/6, tanks on 3/5/7. A mixed variant carries HARM on 2/8 with Mk 84 on 3/7.
- **Walleye (F/A-18A, VFA-195/CVW-5 Midway, 1991):**
  - Walleye I ER on 2/8, tanks on 3/7, AN/AWW-9A data-link pod on 5, AAS-38 on 4.
  - An F/A-18A also used a Walleye II at Umm Qasr (Wikipedia). Its station is not documented.
- **AGM-65E:** on 2/8 (LAU-117); LAU-117 is allowed on 2/3/7/8.
- **USMC F/A-18D "Fast FAC" (C/D era, shown for reference only):** LAU-10 or LAU-68D/A on VERs at 2/8, with the AAR-50 or AAS-38.

## 5. What "A+" and "A++" mean (era tags)

- **A+:** Wikipedia says A-models that received the AN/APG-73 and AMRAAM capability became F/A-18A+. Later USMC life-extension work produced the F/A-18A++.
- **ECP-583** (USMC F/A-18A+ upgrade): avionics and hardware that make the A+ "compatible with a Lot XVII F/A-18C". About 56 aircraft were covered (USMC Concepts & Programs 2010). The 1999 congressional testimony describes the modified A as having "the very same capabilities as a Lot 17 F/A-18C". **I saw both of these only as search snippets.**
- **ECP-560: I found no public reference at all.** The only related item is ECP-620 (2011), the APG-73 retrofit into A+/C/D. It also appeared only as a search snippet.
- Era tag in the JSON:
  - `A+ upgrade` on AIM-120, AIM-9X, JDAM, JSOW, SLAM, AGM-65F, GBU-24, LITENING and BRU-55 means "post-A/B-baseline, plausibly carried by A+".
  - **Only AIM-120 (Wikipedia) and LITENING (USMC legacy Hornets, from 2005-06) have even indirect A+ evidence.** The rest are inferred from "Lot XVII C equivalence" and marked low confidence.

## 6. Where sources disagree

- **Gun rounds:**
  - 578, the maximum drum capacity: AO 1990, FAS M61 page, Wikipedia.
  - 570 and 400 as loaded configurations: NATOPS.
  - **520**: FAS F/A-18 page.
  - Gun weight: 283 lb (AO) vs 255 lb (USAF WF).
- **AIM-7M length:** 144 in (designation-systems) vs 147 in (USAF WF).
- **AIM-9X span:** 11 in (designation-systems) vs 13.9 in wing / 17.5 in fin (USAF WF).
- **HARM wingspan:** 44 in / 1.12 m (designation-systems) vs FAS "3 ft 8 in (101.6 cm)". The FAS figure is internally inconsistent.
- **Harpoon (air-launched):**

  | Source | Length | Weight |
  |---|---|---|
  | designation-systems (D) | 151.5 in (3.85 m) | 1,200 lb (540 kg) |
  | USAF WF (C) | 151 in | 1,160 lb |
  | FAS | 3.79 m | 1,145 lb |

- **GBU-10 weight:** 2,110 lb (designation-systems and WF) vs 2,562 lb (FAS, probably wrong).
- **GBU-24 deployed span:** 81.6 in (WF) vs 2.00 m / 78.75 in (designation-systems).
- **Mk 82 LDGP:** 531 lb / 86.9 in (AO Navy table) vs 502 lb / 89.44 in (USAF WF) vs 2.21 m (Wikipedia).
- **FPU-8/A capacity:** 330 gal (NATOPS, Wikipedia) vs "350 Gal." (designation-systems equipment list).
- **Total external load:** 13,700 lb vs 7,031 kg (see §3).

## 7. Not verified (deliberately left blank or marked "unverified")

- **Store lengths and diameters:**
  - Fuel tanks: no public drawing found. Weights come from the NATOPS Fig 4-4 configuration weights, and the slash notation is my interpretation.
  - Pods: AN/ASQ-173, AN/AWW-9/13, AN/ALQ-167, ACMI.
  - Racks and pylons: SUU-62/63, BRU-32/33, LAU-7, LAU-116, LAU-127.
  - LAU-10 dimensions.
  - Mk 77 dimensions.
  - Mk 80 conical and Snakeye fin spans.
  - AIM-9L/M canard span.
- **Stations for:** Harpoon, SLAM, Walleye II, all LGBs (GBU-10/12/16/24), JDAM, JSOW, TALD (Wikipedia mentions TERs), Snakeye, Mk 83 MAU-91, CBU-59, CBU-78, LAU-61, nuclear weapons (B57, B61, B43), practice bombs and their racks, MER/TER loads, AN/ALQ-167.
  - LGB note: A/B use relied on off-board laser designation, because the A/B-era AAS-38 had no laser.
  - Nuclear note: FAS lists B-57/B-61 for the Hornet, and Wikipedia lists the B43 and B61. Which B61 mods the Navy Hornet carried is unknown.
  - MER/TER note: NATOPS mentions MERs/TERs and has a "MER-7" CG entry.
- **Gun:** the exact longitudinal position of the muzzle. The port is the gun blast diffuser on the upper nose, just forward of the windscreen.
- **Colours:** the Navy colour-band code is documented (yellow = HE, brown = rocket motor, blue = inert, thermal-protected bombs have two yellow nose bands and a bumpy coating). Missile body colours (white vs grey) and guidance-kit colours are not verified per variant.
- **Mines** (Mk 36/40/41 destructors, Quickstrike), CBU-87/89/97, SUU-25, and the tow-banner adapter (TDU-32/B, mounted on the hook): none has documented A/B station data, so they are not in the JSON. CBU-87/89 appear in the FAS C/D list.

## 8. Foreign-only weapons and equipment (excluded from the JSON)

- AIM-132 ASRAAM: RAAF F/A-18A/B.
- IRIS-T: Spanish EF-18M.
- Taurus KEPD 350: Spanish EF-18M.
- GBU-48 (Enhanced Paveway II): certified on Spanish EF-18M in the Spanish MLU.
- BPG-2000 penetrator: Spanish, mentioned on the Wikipedia GBU-24 page. EF-18 carriage was not confirmed in the sources I read.
- AGM-158 JASSM: Finnish F/A-18C/D MLU-2. It is a US weapon but was never used on USN/USMC legacy Hornets.
- CRV-7 rockets: Canadian CF-18.
- Litening III: Spanish EF-18.
- Canadian "fat" ECM pylon on stations 2/8: CF-18.
