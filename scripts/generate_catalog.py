"""Generate the extended catalog: apps/api/catalog_extended.py.

WHY THIS EXISTS
---------------
The hand-authored catalog in products.py is forty SKUs and carries the
adversarial injection payloads. It stays exactly as it is: those forty
prices are frozen, and scripts/verify_catalog.py enforces every one.

What it cannot do is support a comparison. Ask for a cricket bat and
there are two; ask for headphones and there are two; ask for a yoga mat
and there is nothing, so the matcher returned a cricket ball. A shopper
comparing alternatives needs alternatives to compare, and a demo that
recommends the only candidate is not recommending anything.

So this writes a second module of realistic products, deliberately dense
inside each need: eleven cricket bats spanning Rs 899 to Rs 24,999 with
different willow, weight and skill level, so "cricket bat under 3000" has
a genuine shortlist with genuine trade-offs.

Every price here is an integer in paise. Nothing is random at runtime:
this script is deterministic, and the file it writes is committed and
reviewable, because a catalog generated at import time is a catalog
nobody can check.

    python scripts/generate_catalog.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "apps" / "api" / "catalog_extended.py"

# ---------------------------------------------------------------------
# Each family is one shopping need. The variants inside it are the
# alternatives a shopper would actually weigh against each other, which
# is what makes a comparison worth showing.
#
#   (sku_prefix, category, family_noun, [ (name, rupees, rating, attrs,
#                                          description) ... ])
# ---------------------------------------------------------------------

FAMILIES: list[tuple[str, str, str, list[tuple]]] = [

    # ============================================================ CRICKET
    ("XBAT", "cricket", "cricket bat", [
        ("Kookaburra Rapid 5.0 Kashmir Willow Bat", 899, 3.4,
         {"material": "kashmir_willow", "weight_g": 1210, "skill_level": "beginner", "age_fit": "12+"},
         "Entry-level Kashmir willow, machine-pressed, ready to play out of the wrapper."),
        ("SG Cobra Xtreme Kashmir Willow Bat", 1249, 3.7,
         {"material": "kashmir_willow", "weight_g": 1190, "skill_level": "beginner", "age_fit": "14+"},
         "Kashmir willow with a mid blade profile, singles-friendly pickup, toe guard fitted."),
        ("SS Vintage Kashmir Willow Bat", 1699, 3.9,
         {"material": "kashmir_willow", "weight_g": 1170, "skill_level": "intermediate", "age_fit": "15+"},
         "Hand-selected Kashmir cleft, six-piece cane handle, full-length anti-scuff sheet."),
        ("MRF Champion Kashmir Willow Bat", 2199, 4.0,
         {"material": "kashmir_willow", "weight_g": 1160, "skill_level": "intermediate", "age_fit": "15+"},
         "Thicker edges than the entry range, sarawak cane handle, pre-knocked face."),
        ("GM Chrome 606 Kashmir Willow Bat", 2799, 4.2,
         {"material": "kashmir_willow", "weight_g": 1150, "skill_level": "intermediate", "age_fit": "16+"},
         "Concave blade for a lighter pickup at full size, double-toe protection."),
        ("Kookaburra Ghost Pro English Willow Bat", 5499, 4.3,
         {"material": "english_willow", "weight_g": 1180, "skill_level": "advanced", "age_fit": "16+"},
         "Grade 4 English willow, nine-piece handle, big edge profile for front-foot play."),
        ("SG Sunny Legend English Willow Bat", 7999, 4.4,
         {"material": "english_willow", "weight_g": 1175, "skill_level": "advanced", "age_fit": "16+"},
         "Grade 3 English willow, 8-10 straight grains, traditional bow, knocked in."),
        ("SS Ton Reserve Edition English Willow Bat", 11499, 4.5,
         {"material": "english_willow", "weight_g": 1185, "skill_level": "advanced", "age_fit": "17+"},
         "Grade 2 cleft with a low middle, semi-oval handle, tournament ready."),
        ("MRF Genius Grand Edition English Willow Bat", 15999, 4.6,
         {"material": "english_willow", "weight_g": 1190, "skill_level": "professional", "age_fit": "17+"},
         "Grade 1 English willow, 10+ grains, thick edges, players-grade profile."),
        ("GM Diamond DXM Original English Willow Bat", 19999, 4.7,
         {"material": "english_willow", "weight_g": 1195, "skill_level": "professional", "age_fit": "18+"},
         "Top grade cleft, hand-picked, D3X toe protection, individually weighed."),
        ("Kookaburra Kahuna Players English Willow Bat", 24999, 4.8,
         {"material": "english_willow", "weight_g": 1200, "skill_level": "professional", "age_fit": "18+"},
         "Players-grade Grade 1 willow, matched to first-class specification."),
    ]),
    ("XBALL", "cricket", "cricket ball", [
        ("Vector X Practice Leather Ball", 349, 3.3,
         {"ball_type": "leather", "colour": "red", "pack_size": 1},
         "Two-piece practice ball for nets, alum-tanned leather, machine stitched."),
        ("SG Club Leather Ball (Pack of 2)", 749, 3.8,
         {"ball_type": "leather", "colour": "red", "pack_size": 2},
         "Four-piece club-grade ball, hand stitched, holds shape through a full innings."),
        ("Kookaburra County Match Ball", 1499, 4.3,
         {"ball_type": "leather", "colour": "red", "pack_size": 1},
         "Four-piece match ball, hand stitched, prominent seam for swing bowling."),
        ("SG Tournament White Leather Ball", 1199, 4.1,
         {"ball_type": "leather", "colour": "white", "pack_size": 1},
         "White match ball for limited-overs cricket under lights."),
        ("Cosco Wind Ball (Pack of 6)", 449, 3.5,
         {"ball_type": "synthetic", "colour": "assorted", "pack_size": 6},
         "Lightweight practice balls for indoor and street play."),
        ("SS Tennis Cricket Ball (Pack of 6)", 599, 3.6,
         {"ball_type": "tennis", "colour": "assorted", "pack_size": 6},
         "Heavy-duty tennis balls for tape-ball and gully cricket."),
    ]),
    ("XPAD", "cricket", "batting pads", [
        ("Vector X Club Batting Pads", 1099, 3.4,
         {"protection": "club", "hand": "right", "closure": "velcro"},
         "Lightweight PVC facing with three straps, sized for senior play."),
        ("SG Campus Batting Pads", 1799, 3.9,
         {"protection": "club", "hand": "right", "closure": "velcro"},
         "High-density foam bolsters, cane inserts, moulded instep."),
        ("SS Aerolite Batting Pads", 2999, 4.2,
         {"protection": "match", "hand": "right", "closure": "velcro"},
         "Cane and HDF construction, ventilated knee roll, under 1.1 kg per pad."),
        ("Kookaburra Pro Players Batting Pads", 5499, 4.6,
         {"protection": "professional", "hand": "right", "closure": "velcro"},
         "Players-grade cane, cotton-lined, contoured for running between wickets."),
    ]),
    ("XGLV", "cricket", "batting gloves", [
        ("Vector X Club Batting Gloves", 699, 3.3,
         {"protection": "club", "hand": "right", "palm": "pvc"},
         "PVC palm with sausage-finger protection, ventilated back."),
        ("SG Test Batting Gloves", 1499, 4.0,
         {"protection": "match", "hand": "right", "palm": "leather"},
         "Sheep leather palm, high-density foam, towelling thumb."),
        ("SS Players Batting Gloves", 2799, 4.4,
         {"protection": "professional", "hand": "right", "palm": "leather"},
         "Pittards leather palm, split-finger design, moisture-wicking lining."),
    ]),
    ("XHELM", "cricket", "cricket helmet", [
        ("Vector X Steel Grille Helmet", 1299, 3.5,
         {"grille": "steel", "shell": "abs", "certified": "no"},
         "ABS shell with steel grille, adjustable rear dial, junior and senior sizes."),
        ("SG Aeroshield Cricket Helmet", 2699, 4.1,
         {"grille": "steel", "shell": "abs", "certified": "yes"},
         "Meets BS7928:2013, adjustable grille height, breathable padding."),
        ("Shrey Master Class Air Titanium Helmet", 6999, 4.7,
         {"grille": "titanium", "shell": "carbon_composite", "certified": "yes"},
         "Titanium grille, BS7928:2013 certified, neck protector compatible."),
    ]),
    ("XSHOE", "cricket", "cricket shoes", [
        ("Vector X Turf Cricket Shoes", 1199, 3.4,
         {"sole": "rubber", "surface": "turf", "closure": "lace"},
         "Rubber-studded sole for matting and turf, mesh upper."),
        ("SG Sierra Cricket Shoes", 2399, 4.0,
         {"sole": "rubber", "surface": "all_surface", "closure": "lace"},
         "Cushioned midsole, reinforced toe for bowlers, breathable mesh."),
        ("Puma 22 FH Rubber Cricket Shoes", 4499, 4.4,
         {"sole": "rubber", "surface": "all_surface", "closure": "lace"},
         "EVA midsole, external heel counter, lightweight at 320 g."),
        ("Adidas Howzat Spike Cricket Shoes", 6999, 4.5,
         {"sole": "spike", "surface": "grass", "closure": "lace"},
         "Eight-spike outsole for grass wickets, torsion support through the arch."),
    ]),
    ("XKIT", "cricket", "cricket kit bag", [
        ("Vector X Duffle Cricket Bag", 1299, 3.6,
         {"capacity_l": 60, "wheels": False, "compartments": 2},
         "Shoulder duffle sized for a full senior kit, separate shoe pocket."),
        ("SG Ecoflex Wheelie Cricket Bag", 3499, 4.2,
         {"capacity_l": 90, "wheels": True, "compartments": 4},
         "Wheeled kit bag with a bat sleeve, ventilated shoe compartment."),
        ("SS Players Wheelie Cricket Bag", 5999, 4.5,
         {"capacity_l": 110, "wheels": True, "compartments": 5},
         "Tournament-size wheelie with reinforced base and telescopic handle."),
    ]),
    ("XSTMP", "cricket", "cricket stumps", [
        ("Cosco Wooden Stump Set", 649, 3.4,
         {"material": "wood", "set": "3_stumps_2_bails", "spring_back": False},
         "Standard senior wooden stumps with bails, for practice and gully play."),
        ("SG Spring-Back Stump Set", 2199, 4.3,
         {"material": "plastic", "set": "3_stumps_2_bails", "spring_back": True},
         "Spring-loaded base returns the stumps upright, no ground fixing needed."),
    ]),
    ("XGRIP", "cricket", "bat grip", [
        ("Chevron Bat Grip (Pack of 2)", 299, 3.7,
         {"grip_type": "chevron", "pack_size": 2},
         "Standard chevron rubber grips, fits all senior handles."),
        ("SG Players Octopus Grip", 449, 4.1,
         {"grip_type": "octopus", "pack_size": 2},
         "Textured octopus pattern for wet-weather grip."),
        ("SS Grip Cone and Applicator", 399, 3.9,
         {"grip_type": "tool", "pack_size": 1},
         "Cone applicator for fitting grips without a second pair of hands."),
    ]),

    # ============================================================ FITNESS
    ("XYOGA", "fitness", "yoga mat", [
        ("Boldfit Basic Yoga Mat 4mm", 599, 3.6,
         {"thickness_mm": 4, "material": "pvc", "length_cm": 173, "anti_slip": True},
         "Four-millimetre PVC mat with a textured anti-slip face, rolls to a carry strap."),
        ("Kobo NBR Yoga Mat 6mm", 899, 3.9,
         {"thickness_mm": 6, "material": "nbr", "length_cm": 183, "anti_slip": True},
         "Six-millimetre NBR foam for joint comfort on hard floors, closed-cell surface."),
        ("Strauss TPE Yoga Mat 6mm", 1299, 4.1,
         {"thickness_mm": 6, "material": "tpe", "length_cm": 183, "anti_slip": True},
         "Recyclable TPE, double-sided alignment lines, latex free."),
        ("Decathlon Domyos Comfort Yoga Mat 8mm", 1799, 4.3,
         {"thickness_mm": 8, "material": "tpe", "length_cm": 185, "anti_slip": True},
         "Eight-millimetre cushioning for restorative practice, high-density core."),
        ("Nivia Pro Grip Yoga Mat 6mm", 1499, 4.0,
         {"thickness_mm": 6, "material": "pu_rubber", "length_cm": 183, "anti_slip": True},
         "Polyurethane top over a natural rubber base, grips when damp."),
        ("Liforme Travel Yoga Mat 2mm", 4999, 4.7,
         {"thickness_mm": 2, "material": "natural_rubber", "length_cm": 185, "anti_slip": True},
         "Travel-weight natural rubber with etched alignment markers, folds into a bag."),
    ]),
    ("XDUMB", "fitness", "dumbbells", [
        ("Kore PVC Dumbbell Set 2kg Pair", 549, 3.5,
         {"weight_kg": 2, "material": "pvc", "adjustable": False},
         "Vinyl-coated pair for light conditioning and rehabilitation work."),
        ("Boldfit Hex Dumbbell 5kg Pair", 1499, 4.1,
         {"weight_kg": 5, "material": "rubber", "adjustable": False},
         "Rubber-encased hex heads that do not roll, knurled chrome handle."),
        ("Kore Adjustable Dumbbell Set 20kg", 2999, 4.2,
         {"weight_kg": 20, "material": "cast_iron", "adjustable": True},
         "Spin-lock adjustable pair with cast-iron plates, 2 kg to 10 kg per hand."),
        ("Decathlon Corength Adjustable Dumbbells 30kg", 5999, 4.4,
         {"weight_kg": 30, "material": "cast_iron", "adjustable": True},
         "Full adjustable set with a connecting bar for barbell use."),
    ]),
    ("XBAND", "fitness", "resistance bands", [
        ("Boldfit Resistance Loop Bands (Set of 5)", 399, 3.8,
         {"resistance": "5_levels", "material": "latex", "pack_size": 5},
         "Five graded latex loops from extra-light to extra-heavy, with a mesh bag."),
        ("Strauss Tube Resistance Band with Handles", 699, 3.9,
         {"resistance": "medium", "material": "latex_tube", "pack_size": 1},
         "Tube band with foam handles and a door anchor for pulling movements."),
        ("Kore Pull-Up Assist Band Set", 1499, 4.3,
         {"resistance": "4_levels", "material": "latex", "pack_size": 4},
         "Heavy loop bands rated 7 kg to 55 kg for assisted pull-ups and mobility."),
    ]),
    ("XROPE", "fitness", "skipping rope", [
        ("Boldfit Speed Skipping Rope", 299, 3.9,
         {"rope_type": "pvc", "adjustable": True, "bearings": "ball"},
         "Ball-bearing handles with an adjustable PVC cable for double-unders."),
        ("Kore Weighted Skipping Rope", 699, 4.1,
         {"rope_type": "pvc_weighted", "adjustable": True, "bearings": "ball"},
         "Weighted handles for conditioning work, tangle-resistant cable."),
    ]),
    ("XROLL", "fitness", "foam roller", [
        ("Strauss Grid Foam Roller 33cm", 899, 4.0,
         {"length_cm": 33, "density": "medium", "texture": "grid"},
         "Hollow-core grid roller for calves and quads, holds shape under load."),
        ("Kore High-Density Foam Roller 45cm", 1299, 4.2,
         {"length_cm": 45, "density": "high", "texture": "smooth"},
         "Longer roller that spans the spine for thoracic mobility."),
    ]),
    ("XBOTL", "fitness", "water bottle", [
        ("Milton Steel Water Bottle 750ml", 549, 4.0,
         {"capacity_ml": 750, "material": "stainless_steel", "insulated": False},
         "Single-wall stainless bottle with a leak-proof cap."),
        ("Borosil Hydra Vacuum Bottle 1L", 1199, 4.4,
         {"capacity_ml": 1000, "material": "stainless_steel", "insulated": True},
         "Double-wall vacuum insulation, holds temperature for eighteen hours."),
        ("Cello Sports Sipper 1L", 349, 3.6,
         {"capacity_ml": 1000, "material": "tritan", "insulated": False},
         "BPA-free sipper with a flip nozzle for training sessions."),
    ]),

    # ======================================================== ELECTRONICS
    ("XEAR", "electronics", "earbuds", [
        ("boAt Airdopes 141 Wireless Earbuds", 1299, 3.8,
         {"form": "tws", "anc": False, "battery_h": 42, "driver_mm": 8},
         "True wireless earbuds with 42 hours total playback and low-latency gaming mode."),
        ("Realme Buds Air 5 Wireless Earbuds", 2799, 4.1,
         {"form": "tws", "anc": True, "battery_h": 38, "driver_mm": 11},
         "Active noise cancellation to 45 dB, 11 mm drivers, fast pair."),
        ("OnePlus Nord Buds 3 Pro", 3999, 4.3,
         {"form": "tws", "anc": True, "battery_h": 44, "driver_mm": 12},
         "Dual drivers with 49 dB adaptive ANC and Bluetooth 5.4."),
        ("Samsung Galaxy Buds FE", 5999, 4.4,
         {"form": "tws", "anc": True, "battery_h": 30, "driver_mm": 12},
         "One-touch pairing across Galaxy devices, ANC with ambient passthrough."),
        ("Sony WF-C700N Wireless Earbuds", 8999, 4.5,
         {"form": "tws", "anc": True, "battery_h": 15, "driver_mm": 5},
         "Compact ANC earbuds with DSEE upscaling and multipoint connection."),
        ("Apple AirPods Pro (2nd generation)", 21999, 4.8,
         {"form": "tws", "anc": True, "battery_h": 30, "driver_mm": 11},
         "Adaptive audio, transparency mode, USB-C charging case with speaker."),
    ]),
    ("XHDPH", "electronics", "headphones", [
        ("boAt Rockerz 450 On-Ear Headphones", 1499, 3.7,
         {"form": "on_ear", "anc": False, "battery_h": 15, "driver_mm": 40},
         "Foldable on-ear with 40 mm drivers and fifteen hours of playback."),
        ("JBL Tune 520BT Wireless Headphones", 3499, 4.1,
         {"form": "on_ear", "anc": False, "battery_h": 57, "driver_mm": 33},
         "Pure Bass sound, 57 hours of playback, speed charge to three hours in five minutes."),
        ("Sennheiser HD 250BT Over-Ear Headphones", 5999, 4.3,
         {"form": "over_ear", "anc": False, "battery_h": 25, "driver_mm": 32},
         "Closed-back wireless with AAC and aptX Low Latency."),
        ("Sony WH-CH720N Over-Ear Headphones", 8999, 4.4,
         {"form": "over_ear", "anc": True, "battery_h": 35, "driver_mm": 30},
         "Lightweight ANC over-ear at 192 g with multipoint pairing."),
        ("Bose QuietComfort 45 Headphones", 24999, 4.7,
         {"form": "over_ear", "anc": True, "battery_h": 24, "driver_mm": 40},
         "Reference-grade noise cancellation with aware mode and 24-hour battery."),
        ("Sony WH-1000XM5 Wireless Headphones", 29999, 4.8,
         {"form": "over_ear", "anc": True, "battery_h": 30, "driver_mm": 30},
         "Eight-microphone ANC array, speak-to-chat, 30-hour battery."),
    ]),
    ("XPWR", "electronics", "power bank", [
        ("Mi Power Bank 3i 10000mAh", 1299, 4.0,
         {"capacity_mah": 10000, "output_w": 18, "ports": 2},
         "Dual-port 18 W output with pass-through charging and a metal shell."),
        ("Ambrane Stylo 20000mAh Power Bank", 1999, 4.1,
         {"capacity_mah": 20000, "output_w": 22, "ports": 3},
         "Twenty thousand milliamp-hours with 22.5 W fast charge and USB-C in-out."),
        ("Anker PowerCore 20000 PD", 4499, 4.5,
         {"capacity_mah": 20000, "output_w": 65, "ports": 3},
         "65 W Power Delivery, charges a laptop and a phone at once."),
    ]),
    ("XCBL", "electronics", "charging cable", [
        ("boAt Type-C to Type-C Cable 1m", 349, 3.8,
         {"connector": "c_to_c", "length_m": 1, "watt": 60},
         "Braided 60 W cable rated for 10,000 bends."),
        ("Portronics Konnect L 3A Lightning Cable", 449, 3.9,
         {"connector": "usb_a_to_lightning", "length_m": 1.2, "watt": 15},
         "MFi-style nylon-braided cable with an aluminium housing."),
        ("Anker PowerLine III USB-C 1.8m", 1299, 4.4,
         {"connector": "c_to_c", "length_m": 1.8, "watt": 100},
         "100 W USB-C cable with an E-marker chip for laptop charging."),
    ]),
    ("XCHG", "electronics", "wall charger", [
        ("Mi 33W SonicCharge Adapter", 999, 4.1,
         {"output_w": 33, "ports": 1, "gan": False},
         "Single-port 33 W adapter with a foldable pin."),
        ("Ambrane 65W GaN Charger", 1899, 4.3,
         {"output_w": 65, "ports": 3, "gan": True},
         "Gallium nitride 65 W with two USB-C and one USB-A, compact enough for a laptop bag."),
        ("Anker Nano II 100W GaN Charger", 4999, 4.6,
         {"output_w": 100, "ports": 2, "gan": True},
         "100 W GaN III charger that replaces a laptop brick."),
    ]),
    ("XMOUS", "electronics", "mouse", [
        ("Dell MS116 Wired Optical Mouse", 499, 3.9,
         {"connection": "wired", "dpi": 1000, "buttons": 3},
         "Plug-and-play optical mouse with a 1.8 m cable."),
        ("Logitech M235 Wireless Mouse", 999, 4.2,
         {"connection": "wireless_2_4g", "dpi": 1000, "buttons": 3},
         "Twelve-month battery on a single AA, nano receiver."),
        ("Logitech MX Master 3S Wireless Mouse", 8999, 4.8,
         {"connection": "bluetooth", "dpi": 8000, "buttons": 7},
         "Eight-thousand DPI sensor, MagSpeed scroll, works across three machines."),
        ("Razer DeathAdder V3 Gaming Mouse", 5999, 4.6,
         {"connection": "wired", "dpi": 30000, "buttons": 6},
         "Focus Pro 30K sensor at 59 g, optical switches rated to 90 million clicks."),
    ]),
    ("XKEYB", "electronics", "keyboard", [
        ("Dell KB216 Wired Keyboard", 799, 3.9,
         {"switch": "membrane", "layout": "full", "connection": "wired"},
         "Full-size membrane keyboard with a spill-resistant base."),
        ("Logitech K380 Bluetooth Keyboard", 2799, 4.4,
         {"switch": "scissor", "layout": "compact", "connection": "bluetooth"},
         "Multi-device Bluetooth keyboard that switches between three machines."),
        ("Keychron K2 Mechanical Keyboard", 7999, 4.6,
         {"switch": "gateron_brown", "layout": "75_percent", "connection": "bluetooth"},
         "Hot-swappable 75 percent mechanical with white backlight and Mac and Windows keycaps."),
        ("Logitech MX Keys Mini", 9999, 4.7,
         {"switch": "scissor", "layout": "compact", "connection": "bluetooth"},
         "Backlit low-profile keys with proximity sensing and USB-C charging."),
    ]),
    ("XMON", "electronics", "monitor", [
        ("Acer Nitro 22 inch Full HD Monitor", 7499, 4.0,
         {"size_in": 22, "resolution": "1920x1080", "refresh_hz": 75, "panel": "ips"},
         "Twenty-two inch IPS at 75 Hz with FreeSync and thin bezels."),
        ("Dell S2421HN 24 inch IPS Monitor", 10999, 4.3,
         {"size_in": 24, "resolution": "1920x1080", "refresh_hz": 75, "panel": "ips"},
         "Twenty-four inch IPS with dual HDMI and a three-year warranty."),
        ("LG 27 inch QHD IPS Monitor", 18999, 4.5,
         {"size_in": 27, "resolution": "2560x1440", "refresh_hz": 75, "panel": "ips"},
         "Twenty-seven inch QHD with sRGB 99 percent coverage for colour work."),
        ("Samsung Odyssey G5 27 inch Gaming Monitor", 22999, 4.6,
         {"size_in": 27, "resolution": "2560x1440", "refresh_hz": 165, "panel": "va"},
         "165 Hz curved VA panel with 1 ms response and HDR10."),
    ]),
    ("XSPK", "electronics", "bluetooth speaker", [
        ("boAt Stone 350 Bluetooth Speaker", 1799, 4.0,
         {"output_w": 10, "battery_h": 12, "ip_rating": "IPX7"},
         "Ten-watt IPX7 speaker with twelve hours of playback."),
        ("JBL Flip 6 Portable Speaker", 8999, 4.6,
         {"output_w": 30, "battery_h": 12, "ip_rating": "IP67"},
         "Thirty-watt two-way system, IP67 dust and water rating, PartyBoost pairing."),
        ("Marshall Emberton II Speaker", 14999, 4.7,
         {"output_w": 20, "battery_h": 30, "ip_rating": "IP67"},
         "True Stereophonic sound with thirty hours of playback."),
    ]),
    ("XWTCH", "electronics", "smartwatch", [
        ("Noise ColorFit Pulse 3 Smartwatch", 1799, 3.8,
         {"display_in": 1.96, "gps": False, "battery_d": 7},
         "Bluetooth calling, sixty sports modes, seven-day battery."),
        ("Fire-Boltt Phoenix Pro Smartwatch", 2499, 3.9,
         {"display_in": 1.39, "gps": False, "battery_d": 8},
         "Round AMOLED with SpO2 and heart-rate tracking."),
        ("Amazfit Bip 5 Smartwatch", 5999, 4.3,
         {"display_in": 1.91, "gps": True, "battery_d": 10},
         "Built-in GPS, ten-day battery, Zepp OS with offline maps."),
        ("Samsung Galaxy Watch6 40mm", 24999, 4.6,
         {"display_in": 1.3, "gps": True, "battery_d": 2},
         "Wear OS with body composition, ECG and sleep coaching."),
    ]),
    ("XLAP", "electronics", "laptop", [
        ("Lenovo IdeaPad Slim 1 Celeron 8GB", 24999, 3.8,
         {"cpu": "intel_celeron", "ram_gb": 8, "storage_gb": 256, "screen_in": 14},
         "Fourteen-inch everyday laptop for browsing, documents and video calls."),
        ("HP 15s Ryzen 5 8GB 512GB", 42999, 4.1,
         {"cpu": "ryzen_5", "ram_gb": 8, "storage_gb": 512, "screen_in": 15.6},
         "Ryzen 5 with 512 GB NVMe, micro-edge display, backlit keyboard."),
        ("Dell Inspiron 14 Core i5 16GB", 58999, 4.3,
         {"cpu": "intel_i5", "ram_gb": 16, "storage_gb": 512, "screen_in": 14},
         "Thirteenth-gen i5 with 16 GB dual-channel memory for development work."),
        ("Lenovo Yoga Slim 6 Core i7 16GB", 78999, 4.5,
         {"cpu": "intel_i7", "ram_gb": 16, "storage_gb": 1024, "screen_in": 14},
         "OLED 14-inch, 1 TB storage, 1.3 kg chassis with 70 Wh battery."),
        ("Apple MacBook Air M2 8GB 256GB", 89999, 4.8,
         {"cpu": "apple_m2", "ram_gb": 8, "storage_gb": 256, "screen_in": 13.6},
         "M2 with an eight-core CPU, fanless, eighteen-hour battery."),
    ]),
    ("XWCAM", "electronics", "webcam", [
        ("Zebronics Zeb-Crystal Pro Webcam", 899, 3.6,
         {"resolution": "1080p", "fps": 30, "mic": True},
         "Full HD webcam with a built-in microphone and a manual focus ring."),
        ("Logitech C920 HD Pro Webcam", 6499, 4.6,
         {"resolution": "1080p", "fps": 30, "mic": True},
         "Glass lens with stereo mics and automatic light correction."),
    ]),

    # ============================================================== BOOKS
    ("XALGO", "books", "algorithms book", [
        ("Grokking Algorithms — Aditya Bhargava", 549, 4.6,
         {"topic": "algorithms", "level": "beginner", "pages": 256, "format": "paperback"},
         "Illustrated introduction to sorting, search, graphs and dynamic programming."),
        ("Algorithms Unlocked — Thomas H. Cormen", 899, 4.3,
         {"topic": "algorithms", "level": "beginner", "pages": 240, "format": "paperback"},
         "A plain-language tour of the algorithms behind everyday computing."),
        ("Data Structures and Algorithms Made Easy — Narasimha Karumanchi", 749, 4.4,
         {"topic": "algorithms", "level": "intermediate", "pages": 434, "format": "paperback"},
         "Problem-and-solution format covering every standard interview data structure."),
        ("The Algorithm Design Manual — Steven Skiena", 3299, 4.7,
         {"topic": "algorithms", "level": "intermediate", "pages": 810, "format": "hardcover"},
         "Design techniques plus a catalogue of algorithmic problems and where they appear."),
        ("Introduction to Algorithms — Cormen, Leiserson, Rivest, Stein", 4799, 4.8,
         {"topic": "algorithms", "level": "advanced", "pages": 1312, "format": "hardcover"},
         "The reference text. Rigorous treatment of algorithm design and analysis."),
        ("Competitive Programming 4 — Halim and Halim", 3899, 4.5,
         {"topic": "algorithms", "level": "advanced", "pages": 460, "format": "paperback"},
         "Contest techniques, from ad-hoc problems to advanced graph and geometry work."),
    ]),
    ("XPROG", "books", "programming book", [
        ("Clean Code — Robert C. Martin", 1499, 4.5,
         {"topic": "software_craft", "level": "intermediate", "pages": 464, "format": "paperback"},
         "A handbook of agile software craftsmanship, with worked refactorings."),
        ("The Pragmatic Programmer — Hunt and Thomas", 2299, 4.7,
         {"topic": "software_craft", "level": "intermediate", "pages": 352, "format": "hardcover"},
         "Twentieth-anniversary edition on the practice of writing software well."),
        ("Designing Data-Intensive Applications — Martin Kleppmann", 3499, 4.8,
         {"topic": "systems", "level": "advanced", "pages": 616, "format": "paperback"},
         "The reasoning behind reliable, scalable and maintainable data systems."),
        ("Fluent Python — Luciano Ramalho", 3999, 4.7,
         {"topic": "python", "level": "advanced", "pages": 1012, "format": "paperback"},
         "Second edition, covering the data model, concurrency and type hints."),
        ("Python Crash Course — Eric Matthes", 1799, 4.6,
         {"topic": "python", "level": "beginner", "pages": 552, "format": "paperback"},
         "A project-based introduction, third edition."),
        ("System Design Interview Volume 1 — Alex Xu", 1999, 4.4,
         {"topic": "systems", "level": "intermediate", "pages": 322, "format": "paperback"},
         "An insider's guide to large-scale system design questions."),
    ]),
    ("XFICT", "books", "fiction book", [
        ("The Midnight Library — Matt Haig", 399, 4.2,
         {"topic": "fiction", "level": "general", "pages": 304, "format": "paperback"},
         "A novel about the lives you did not live."),
        ("Project Hail Mary — Andy Weir", 599, 4.7,
         {"topic": "science_fiction", "level": "general", "pages": 496, "format": "paperback"},
         "A lone astronaut, an impossible problem, and one very unexpected colleague."),
        ("The Song of Achilles — Madeline Miller", 449, 4.5,
         {"topic": "fiction", "level": "general", "pages": 352, "format": "paperback"},
         "The Iliad retold through Patroclus."),
        ("Klara and the Sun — Kazuo Ishiguro", 549, 4.1,
         {"topic": "fiction", "level": "general", "pages": 320, "format": "paperback"},
         "An artificial friend observes the family that buys her."),
    ]),
    ("XBIZ", "books", "business book", [
        ("Atomic Habits — James Clear", 549, 4.6,
         {"topic": "productivity", "level": "general", "pages": 320, "format": "paperback"},
         "An easy and proven way to build good habits and break bad ones."),
        ("Thinking, Fast and Slow — Daniel Kahneman", 699, 4.5,
         {"topic": "psychology", "level": "general", "pages": 499, "format": "paperback"},
         "The two systems that drive the way we think."),
        ("Zero to One — Peter Thiel", 449, 4.3,
         {"topic": "startups", "level": "general", "pages": 224, "format": "paperback"},
         "Notes on startups, or how to build the future."),
        ("The Lean Startup — Eric Ries", 599, 4.2,
         {"topic": "startups", "level": "general", "pages": 336, "format": "paperback"},
         "Continuous innovation as a management discipline."),
    ]),

    # ============================================================ APPAREL
    ("XTSH", "apparel", "t-shirt", [
        ("Basics Cotton Round Neck T-Shirt", 399, 3.7,
         {"fabric": "cotton", "fit": "regular", "sleeve": "half"},
         "Single-jersey cotton tee, pre-shrunk, in six colours."),
        ("Puma Essentials Logo T-Shirt", 899, 4.2,
         {"fabric": "cotton_blend", "fit": "regular", "sleeve": "half"},
         "Cotton-blend tee with a rubberised chest logo."),
        ("Nike Dri-FIT Training T-Shirt", 1799, 4.5,
         {"fabric": "polyester", "fit": "athletic", "sleeve": "half"},
         "Sweat-wicking Dri-FIT knit for training in heat."),
        ("Adidas Aeroready Polo T-Shirt", 2199, 4.4,
         {"fabric": "recycled_polyester", "fit": "regular", "sleeve": "half"},
         "Aeroready polo with a ribbed collar, made with recycled fibres."),
    ]),
    ("XHOOD", "apparel", "hoodie", [
        ("Basics Fleece Pullover Hoodie", 999, 3.8,
         {"fabric": "fleece", "fit": "regular", "hood": "drawstring"},
         "Brushed fleece pullover with a kangaroo pocket."),
        ("Puma Essentials Full-Zip Hoodie", 2299, 4.3,
         {"fabric": "cotton_blend", "fit": "regular", "hood": "drawstring"},
         "Full-zip hoodie with ribbed cuffs and side pockets."),
        ("Nike Sportswear Club Fleece Hoodie", 3499, 4.5,
         {"fabric": "cotton_blend", "fit": "relaxed", "hood": "drawstring"},
         "Midweight club fleece with a double-layer hood."),
    ]),
    ("XJOG", "apparel", "joggers", [
        ("Basics Cotton Joggers", 699, 3.7,
         {"fabric": "cotton", "fit": "regular", "pockets": 2},
         "Elasticated cotton joggers with a drawcord waist."),
        ("Puma Tapered Training Joggers", 1699, 4.2,
         {"fabric": "polyester", "fit": "tapered", "pockets": 2},
         "Tapered fit with zip pockets for gym work."),
        ("Adidas Tiro 23 Training Pants", 2799, 4.5,
         {"fabric": "recycled_polyester", "fit": "tapered", "pockets": 2},
         "Aeroready training pants with ankle zips."),
    ]),
    ("XSNEK", "apparel", "sneakers", [
        ("Campus Oxyfit Running Shoes", 1299, 3.8,
         {"use": "running", "closure": "lace", "sole": "eva"},
         "Lightweight EVA sole with a mesh upper for daily runs."),
        ("Puma Softride Running Shoes", 3499, 4.3,
         {"use": "running", "closure": "lace", "sole": "softride_foam"},
         "Softride foam midsole for road running and gym use."),
        ("Nike Revolution 7 Running Shoes", 4499, 4.4,
         {"use": "running", "closure": "lace", "sole": "foam"},
         "Soft foam midsole with a breathable knit upper."),
        ("Adidas Ultraboost Light Running Shoes", 12999, 4.7,
         {"use": "running", "closure": "lace", "sole": "boost_light"},
         "Light Boost midsole returning energy through the stride."),
    ]),
    ("XSOCK", "apparel", "socks", [
        ("Basics Ankle Socks (Pack of 5)", 349, 3.8,
         {"length": "ankle", "fabric": "cotton", "pack_size": 5},
         "Combed cotton ankle socks with a cushioned sole."),
        ("Puma Crew Socks (Pack of 3)", 699, 4.1,
         {"length": "crew", "fabric": "cotton_blend", "pack_size": 3},
         "Ribbed crew socks with arch support."),
    ]),
    ("XJKT", "apparel", "jacket", [
        ("Basics Windcheater Jacket", 1299, 3.7,
         {"fabric": "nylon", "insulation": "none", "hood": True},
         "Packable windcheater with a concealed hood."),
        ("Wildcraft Rain Jacket", 2499, 4.1,
         {"fabric": "polyester_pu", "insulation": "none", "hood": True},
         "Seam-sealed rain shell rated to 3000 mm water column."),
        ("Columbia Powder Lite Insulated Jacket", 7999, 4.6,
         {"fabric": "nylon", "insulation": "synthetic", "hood": True},
         "Omni-Heat reflective lining with synthetic fill for cold weather."),
    ]),

    # ========================================================= STATIONERY
    ("XPEN", "stationery", "pen", [
        ("Cello Butterflow Ball Pen (Pack of 10)", 149, 3.8,
         {"ink": "ballpoint", "tip_mm": 0.7, "pack_size": 10},
         "Low-viscosity ink that writes without skipping."),
        ("Uni-ball Eye Rollerball Pen (Pack of 3)", 449, 4.4,
         {"ink": "rollerball", "tip_mm": 0.5, "pack_size": 3},
         "Pigment ink that is water and fade resistant."),
        ("Parker Vector Fountain Pen", 1299, 4.5,
         {"ink": "fountain", "tip_mm": 0.5, "pack_size": 1},
         "Stainless steel nib with a converter and two cartridges."),
    ]),
    ("XNOTE", "stationery", "notebook", [
        ("Classmate Ruled Notebook 200 Pages", 199, 3.9,
         {"pages": 200, "ruling": "single_line", "binding": "spiral"},
         "Spiral-bound ruled notebook on 70 GSM paper."),
        ("Moleskine Classic Notebook Large", 1899, 4.6,
         {"pages": 240, "ruling": "dotted", "binding": "hardcover"},
         "Hardcover dotted notebook with an elastic closure and a back pocket."),
        ("Leuchtturm1917 A5 Dotted Notebook", 2299, 4.7,
         {"pages": 251, "ruling": "dotted", "binding": "hardcover"},
         "Numbered pages with a blank index, 80 GSM ink-proof paper."),
    ]),
    ("XMRKR", "stationery", "markers", [
        ("Camlin Whiteboard Marker (Pack of 5)", 249, 3.8,
         {"marker_type": "whiteboard", "tip": "bullet", "pack_size": 5},
         "Low-odour dry-erase markers in assorted colours."),
        ("Faber-Castell Highlighter Set (Pack of 6)", 399, 4.3,
         {"marker_type": "highlighter", "tip": "chisel", "pack_size": 6},
         "Chisel-tip highlighters in six pastel shades."),
    ]),
    ("XDESK", "stationery", "desk organiser", [
        ("Solo Mesh Desk Organiser", 599, 3.9,
         {"compartments": 4, "material": "steel_mesh", "colour": "black"},
         "Four-compartment mesh caddy for pens, notes and clips."),
        ("Bamboo Desk Organiser with Drawer", 1499, 4.3,
         {"compartments": 6, "material": "bamboo", "colour": "natural"},
         "Bamboo organiser with a pull-out drawer and a phone slot."),
    ]),
    ("XPLNR", "stationery", "planner", [
        ("Undated Daily Planner A5", 549, 4.0,
         {"format": "daily", "pages": 200, "dated": False},
         "Undated A5 planner with a monthly overview and habit tracker."),
        ("2026 Academic Weekly Planner", 899, 4.2,
         {"format": "weekly", "pages": 160, "dated": True},
         "Dated weekly planner running July to June with tabbed months."),
    ]),

    # ========================================================== GROCERIES
    ("XTEA", "groceries", "tea", [
        ("Tata Tea Gold 500g", 299, 4.2,
         {"weight_g": 500, "kind": "black_tea", "organic": False},
         "Assam leaf blended with gently rolled leaves."),
        ("Vahdam Himalayan Green Tea 100g", 549, 4.4,
         {"weight_g": 100, "kind": "green_tea", "organic": True},
         "Single-estate Himalayan green tea, harvested and packed at source."),
        ("Twinings Earl Grey Tea Bags (100)", 899, 4.3,
         {"weight_g": 200, "kind": "black_tea", "organic": False},
         "Bergamot-scented black tea in individually sealed bags."),
    ]),
    ("XRICE", "groceries", "rice", [
        ("India Gate Basmati Rice 5kg", 899, 4.3,
         {"weight_g": 5000, "grain": "basmati", "organic": False},
         "Aged basmati with an extra-long grain for biryani and pulao."),
        ("Daawat Rozana Basmati Rice 5kg", 649, 4.0,
         {"weight_g": 5000, "grain": "basmati", "organic": False},
         "Everyday basmati for daily cooking."),
        ("Organic Tattva Brown Rice 1kg", 249, 4.1,
         {"weight_g": 1000, "grain": "brown", "organic": True},
         "Unpolished organic brown rice with the bran intact."),
    ]),
    ("XOIL", "groceries", "cooking oil", [
        ("Fortune Sunlite Refined Sunflower Oil 1L", 199, 4.0,
         {"volume_ml": 1000, "kind": "sunflower", "organic": False},
         "Refined sunflower oil for everyday frying."),
        ("Saffola Gold Blended Oil 1L", 249, 4.2,
         {"volume_ml": 1000, "kind": "blended", "organic": False},
         "Rice bran and sunflower blend."),
        ("Cold-Pressed Groundnut Oil 1L", 549, 4.4,
         {"volume_ml": 1000, "kind": "groundnut", "organic": True},
         "Wood-pressed groundnut oil, unrefined, in a glass bottle."),
    ]),
    ("XSNCK", "groceries", "snacks", [
        ("Roasted Almonds 500g", 649, 4.3,
         {"weight_g": 500, "kind": "nuts", "organic": False},
         "Dry-roasted California almonds, unsalted."),
        ("Mixed Dry Fruits 500g", 899, 4.2,
         {"weight_g": 500, "kind": "dry_fruit", "organic": False},
         "Almonds, cashews, raisins and pistachios in one pack."),
        ("Multigrain Protein Bars (Pack of 6)", 399, 3.9,
         {"weight_g": 300, "kind": "bar", "organic": False},
         "Ten grams of protein per bar, no added refined sugar."),
    ]),
    ("XHONY", "groceries", "honey", [
        ("Dabur Honey 1kg", 449, 4.1,
         {"weight_g": 1000, "kind": "processed", "organic": False},
         "Filtered honey tested against twenty-two quality parameters."),
        ("Raw Forest Honey 500g", 749, 4.5,
         {"weight_g": 500, "kind": "raw", "organic": True},
         "Unheated, unfiltered forest honey that crystallises naturally."),
    ]),
]


# ---------------------------------------------------------------------
# Second block. Same shape, more needs — so that a query outside the
# original six categories lands on something real instead of on the
# nearest token overlap.
# ---------------------------------------------------------------------

FAMILIES += [

    # ============================================================ CRICKET
    ("XWKG", "cricket", "wicket keeping gloves", [
        ("Vector X Club Keeping Gloves", 899, 3.5,
         {"protection": "club", "palm": "rubber"}, "Rubber palm with mesh backing for club keeping."),
        ("SG Club Wicket Keeping Gloves", 1699, 4.0,
         {"protection": "match", "palm": "leather"}, "Leather palm with cotton padding and a towelling cuff."),
        ("SS Professional Keeping Gloves", 3499, 4.4,
         {"protection": "professional", "palm": "leather"}, "Pittards palm, contoured catching web, sweat-absorbent lining."),
    ]),
    ("XGUARD", "cricket", "protective guards", [
        ("Vector X Abdominal Guard", 349, 3.6,
         {"guard": "abdominal", "size": "senior"}, "Moulded polymer guard with a padded rim."),
        ("SG Thigh Guard Combo", 999, 4.0,
         {"guard": "thigh", "size": "senior"}, "Inner and outer thigh pads with adjustable straps."),
        ("SS Arm Guard", 799, 3.9,
         {"guard": "arm", "size": "senior"}, "High-density foam arm guard with a moulded elbow cup."),
        ("SG Chest Guard", 1299, 4.1,
         {"guard": "chest", "size": "senior"}, "Segmented chest protector that moves with the shot."),
    ]),
    ("XNET", "cricket", "practice net", [
        ("Portable Cricket Practice Net 10ft", 2999, 4.0,
         {"length_ft": 10, "portable": True}, "Pop-up net with steel pegs for backyard practice."),
        ("Full Size Cricket Net 30ft", 8999, 4.3,
         {"length_ft": 30, "portable": False}, "Nylon net for a full-length practice lane."),
    ]),
    ("XSCOR", "cricket", "scorebook", [
        ("Cricket Scorebook 60 Innings", 349, 4.0,
         {"innings": 60, "binding": "spiral"}, "Ruled scorebook with bowling and batting analysis grids."),
    ]),

    # ============================================================ FITNESS
    ("XKETT", "fitness", "kettlebell", [
        ("Kore Vinyl Kettlebell 4kg", 799, 3.8,
         {"weight_kg": 4, "coating": "vinyl"}, "Vinyl-coated kettlebell for swings and goblet squats."),
        ("Boldfit Cast Iron Kettlebell 8kg", 1699, 4.2,
         {"weight_kg": 8, "coating": "powder"}, "Single-cast iron bell with a wide, smooth handle."),
        ("Decathlon Corength Kettlebell 12kg", 2799, 4.4,
         {"weight_kg": 12, "coating": "rubber"}, "Rubber base that protects flooring, flat-bottomed."),
    ]),
    ("XGGLV", "fitness", "gym gloves", [
        ("Boldfit Gym Gloves with Wrist Support", 449, 3.9,
         {"wrist_support": True, "material": "microfibre"}, "Padded palm with a wrap-around wrist strap."),
        ("Nivia Predator Gym Gloves", 799, 4.1,
         {"wrist_support": True, "material": "leather"}, "Leather palm with silicone grip dots."),
    ]),
    ("XABRL", "fitness", "ab roller", [
        ("Kore Dual Wheel Ab Roller", 549, 3.9,
         {"wheels": 2, "knee_pad": True}, "Wide dual-wheel roller with a knee pad included."),
        ("Boldfit Ab Wheel with Resistance", 999, 4.2,
         {"wheels": 1, "knee_pad": True}, "Single wide wheel with an internal return spring."),
    ]),
    ("XPULL", "fitness", "pull up bar", [
        ("Doorway Pull Up Bar", 999, 3.8,
         {"mount": "doorway", "max_kg": 100}, "No-screw doorway bar rated to 100 kg."),
        ("Wall Mounted Pull Up Bar", 2499, 4.4,
         {"mount": "wall", "max_kg": 200}, "Steel wall bar with multiple grip positions."),
    ]),
    ("XBLOK", "fitness", "yoga blocks", [
        ("EVA Yoga Block Pair", 499, 4.0,
         {"material": "eva", "pack_size": 2}, "High-density EVA blocks for support in seated poses."),
        ("Cork Yoga Block with Strap", 1099, 4.4,
         {"material": "cork", "pack_size": 1}, "Natural cork block with a cotton stretching strap."),
    ]),
    ("XPROT", "fitness", "protein supplement", [
        ("Whey Protein Concentrate 1kg", 1899, 4.0,
         {"weight_g": 1000, "protein_g": 24}, "Twenty-four grams of protein per scoop, chocolate."),
        ("Optimum Nutrition Gold Standard Whey 2lb", 4499, 4.6,
         {"weight_g": 907, "protein_g": 24}, "Whey isolate blend with added digestive enzymes."),
        ("Plant Protein Blend 1kg", 2299, 4.1,
         {"weight_g": 1000, "protein_g": 22}, "Pea and rice protein blend, unflavoured."),
    ]),

    # ======================================================== ELECTRONICS
    ("XTAB", "electronics", "tablet", [
        ("Lenovo Tab M9 4GB 64GB", 12999, 4.0,
         {"screen_in": 9, "ram_gb": 4, "storage_gb": 64}, "Nine-inch HD tablet for reading and video."),
        ("Samsung Galaxy Tab A9+ 8GB", 22999, 4.3,
         {"screen_in": 11, "ram_gb": 8, "storage_gb": 128}, "Eleven-inch 90 Hz display with quad speakers."),
        ("Apple iPad 10th Gen 64GB", 34999, 4.7,
         {"screen_in": 10.9, "ram_gb": 4, "storage_gb": 64}, "A14 Bionic with a 10.9-inch Liquid Retina display."),
    ]),
    ("XSSD", "electronics", "ssd", [
        ("Crucial BX500 480GB SATA SSD", 2799, 4.3,
         {"capacity_gb": 480, "interface": "sata"}, "2.5-inch SATA drive at up to 540 MB/s read."),
        ("WD Blue SN570 1TB NVMe SSD", 5999, 4.6,
         {"capacity_gb": 1000, "interface": "nvme"}, "PCIe Gen3 NVMe at up to 3500 MB/s read."),
        ("Samsung 990 EVO 1TB NVMe SSD", 8999, 4.7,
         {"capacity_gb": 1000, "interface": "nvme"}, "PCIe Gen4 with Intelligent TurboWrite 2.0."),
    ]),
    ("XUSB", "electronics", "pen drive", [
        ("SanDisk Cruzer Blade 32GB", 349, 4.1,
         {"capacity_gb": 32, "interface": "usb_2"}, "Compact USB 2.0 drive with a retractable body."),
        ("SanDisk Ultra Dual Drive 128GB Type-C", 1299, 4.4,
         {"capacity_gb": 128, "interface": "usb_3_c"}, "Dual USB-A and USB-C connectors for phone and laptop."),
    ]),
    ("XRTR", "electronics", "wifi router", [
        ("TP-Link Archer C6 AC1200 Router", 2199, 4.2,
         {"standard": "wifi_5", "bands": 2}, "Dual-band AC1200 with four external antennas."),
        ("TP-Link Archer AX55 WiFi 6 Router", 5499, 4.5,
         {"standard": "wifi_6", "bands": 2}, "AX3000 WiFi 6 with OFDMA and WPA3."),
    ]),
    ("XSTND", "electronics", "laptop stand", [
        ("Aluminium Laptop Stand Adjustable", 899, 4.1,
         {"material": "aluminium", "adjustable": True}, "Six-level aluminium riser with anti-slip pads."),
        ("Portronics My Buddy K Portable Stand", 1499, 4.3,
         {"material": "aluminium", "adjustable": True}, "Foldable stand that lifts the screen to eye level."),
    ]),
    ("XMIC", "electronics", "microphone", [
        ("Boya BY-M1 Lavalier Microphone", 899, 4.2,
         {"mic_type": "lavalier", "connection": "3_5mm"}, "Omnidirectional clip mic with a 6 m cable."),
        ("Maono AU-A04 USB Condenser Mic", 3499, 4.4,
         {"mic_type": "condenser", "connection": "usb"}, "Cardioid USB mic with a boom arm and pop filter."),
        ("Rode NT-USB Mini", 9999, 4.7,
         {"mic_type": "condenser", "connection": "usb"}, "Studio-quality USB mic with an internal pop shield."),
    ]),
    ("XRING", "electronics", "ring light", [
        ("10 inch Ring Light with Tripod", 1299, 4.0,
         {"diameter_in": 10, "tripod": True}, "Three colour temperatures with a 2.1 m tripod."),
        ("18 inch Studio Ring Light", 4499, 4.4,
         {"diameter_in": 18, "tripod": True}, "Dimmable studio ring light with a phone and camera mount."),
    ]),
    ("XTRIP", "electronics", "tripod", [
        ("Digitek DTR 260 Tripod", 999, 3.9,
         {"height_cm": 155, "load_kg": 3}, "Aluminium tripod extending to 155 cm."),
        ("Manfrotto Compact Action Tripod", 5999, 4.6,
         {"height_cm": 155, "load_kg": 1.5}, "Joystick head for one-handed framing."),
    ]),
    ("XPRNT", "electronics", "printer", [
        ("HP DeskJet 2331 All-in-One Printer", 4499, 4.0,
         {"tech": "inkjet", "functions": 3}, "Print, scan and copy over USB."),
        ("HP Smart Tank 580 Wireless Printer", 13999, 4.4,
         {"tech": "ink_tank", "functions": 3}, "Refillable ink tank with wireless printing."),
        ("Brother HL-B2000D Mono Laser Printer", 11999, 4.5,
         {"tech": "laser", "functions": 1}, "Duplex mono laser at 34 pages per minute."),
    ]),
    ("XCTRL", "electronics", "game controller", [
        ("Redgear Pro Wireless Gamepad", 1799, 4.0,
         {"connection": "wireless", "platform": "pc"}, "Dual-vibration wireless gamepad with a 2.4 GHz dongle."),
        ("Xbox Wireless Controller", 5499, 4.7,
         {"connection": "bluetooth", "platform": "multi"}, "Textured triggers and a hybrid D-pad, works with PC and mobile."),
    ]),

    # ============================================================== BOOKS
    ("XSCI", "books", "science book", [
        ("Cosmos — Carl Sagan", 549, 4.7,
         {"topic": "astronomy", "level": "general", "pages": 396}, "The classic tour of the universe and our place in it."),
        ("A Brief History of Time — Stephen Hawking", 449, 4.5,
         {"topic": "physics", "level": "general", "pages": 212}, "From the big bang to black holes."),
        ("Sapiens — Yuval Noah Harari", 599, 4.6,
         {"topic": "history", "level": "general", "pages": 464}, "A brief history of humankind."),
    ]),
    ("XBIO", "books", "biography", [
        ("Wings of Fire — A.P.J. Abdul Kalam", 299, 4.7,
         {"topic": "biography", "level": "general", "pages": 180}, "An autobiography of India's missile man."),
        ("Steve Jobs — Walter Isaacson", 699, 4.5,
         {"topic": "biography", "level": "general", "pages": 656}, "The authorised biography, from interviews over two years."),
        ("Elon Musk — Walter Isaacson", 899, 4.3,
         {"topic": "biography", "level": "general", "pages": 688}, "A reported account of an unusually public life."),
    ]),
    ("XEXAM", "books", "exam preparation book", [
        ("Quantitative Aptitude — R.S. Aggarwal", 649, 4.4,
         {"topic": "aptitude", "level": "intermediate", "pages": 900}, "Standard aptitude preparation for competitive exams."),
        ("Cracking the Coding Interview — Gayle Laakmann McDowell", 1899, 4.6,
         {"topic": "interview", "level": "intermediate", "pages": 708}, "189 programming questions and solutions."),
    ]),
    ("XKIDS", "books", "childrens book", [
        ("The Gruffalo — Julia Donaldson", 349, 4.8,
         {"topic": "picture_book", "level": "children", "pages": 32}, "A mouse takes a walk through a deep dark wood."),
        ("Matilda — Roald Dahl", 299, 4.7,
         {"topic": "fiction", "level": "children", "pages": 240}, "A small girl with a very large mind."),
    ]),

    # ============================================================ APPAREL
    ("XSHRT", "apparel", "formal shirt", [
        ("Basics Cotton Formal Shirt", 899, 3.8,
         {"fabric": "cotton", "fit": "regular", "sleeve": "full"}, "Wrinkle-resistant cotton shirt with a spread collar."),
        ("Van Heusen Slim Fit Formal Shirt", 1999, 4.3,
         {"fabric": "cotton_blend", "fit": "slim", "sleeve": "full"}, "Slim-fit shirt with a stain-resistant finish."),
    ]),
    ("XJEAN", "apparel", "jeans", [
        ("Basics Straight Fit Jeans", 1199, 3.8,
         {"fit": "straight", "fabric": "denim"}, "Mid-rise straight jeans in stretch denim."),
        ("Levi's 511 Slim Fit Jeans", 3499, 4.5,
         {"fit": "slim", "fabric": "denim_stretch"}, "Slim through the seat and thigh with a narrow leg."),
    ]),
    ("XSHOR", "apparel", "shorts", [
        ("Basics Cotton Shorts", 549, 3.7,
         {"fabric": "cotton", "fit": "regular"}, "Knee-length cotton shorts with an elastic waist."),
        ("Nike Dri-FIT Training Shorts", 1699, 4.4,
         {"fabric": "polyester", "fit": "athletic"}, "Sweat-wicking shorts with a zip pocket."),
    ]),
    ("XCAP", "apparel", "cap", [
        ("Basics Cotton Baseball Cap", 349, 3.7,
         {"style": "baseball", "closure": "strap"}, "Six-panel cotton cap with an adjustable strap."),
        ("Puma Essentials Cap", 899, 4.2,
         {"style": "baseball", "closure": "strap"}, "Embroidered logo cap with a curved brim."),
    ]),
    ("XBKPK", "apparel", "backpack", [
        ("Wildcraft Daypack 25L", 1199, 4.0,
         {"capacity_l": 25, "laptop_sleeve": True}, "Everyday 25-litre pack with a padded laptop sleeve."),
        ("American Tourister Laptop Backpack 32L", 2299, 4.3,
         {"capacity_l": 32, "laptop_sleeve": True}, "Thirty-two-litre pack with an organiser panel."),
        ("Wildcraft Trekking Rucksack 45L", 4499, 4.5,
         {"capacity_l": 45, "laptop_sleeve": False}, "Ventilated back system with a rain cover."),
    ]),

    # ========================================================= STATIONERY
    ("XCALC", "stationery", "calculator", [
        ("Casio FX-82MS Scientific Calculator", 799, 4.5,
         {"kind": "scientific", "functions": 240}, "Two-line display with 240 built-in functions."),
        ("Casio FX-991EX Classwiz", 1699, 4.7,
         {"kind": "scientific", "functions": 552}, "High-resolution display with spreadsheet and QR features."),
    ]),
    ("XFILE", "stationery", "file folder", [
        ("Solo Ring Binder File (Pack of 5)", 449, 3.9,
         {"kind": "ring_binder", "pack_size": 5}, "Two-ring binders with a transparent front pocket."),
        ("Expanding File Folder 13 Pocket", 699, 4.2,
         {"kind": "expanding", "pack_size": 1}, "Thirteen labelled pockets with an elastic closure."),
    ]),
    ("XSTAP", "stationery", "stapler", [
        ("Kangaro HD-10D Stapler with Pins", 249, 4.1,
         {"capacity_sheets": 20, "pins_included": True}, "Half-strip stapler with a box of pins."),
        ("Heavy Duty Stapler 100 Sheets", 1299, 4.3,
         {"capacity_sheets": 100, "pins_included": True}, "Metal-body stapler for thick documents."),
    ]),
    ("XSTKY", "stationery", "sticky notes", [
        ("Sticky Notes Assorted (Pack of 12)", 249, 4.0,
         {"pack_size": 12, "size_mm": "76x76"}, "Twelve pads in six colours, 100 sheets each."),
        ("Post-it Super Sticky Notes (Pack of 6)", 599, 4.5,
         {"pack_size": 6, "size_mm": "76x76"}, "Twice the sticking power, holds on vertical surfaces."),
    ]),
    ("XART", "stationery", "art supplies", [
        ("Faber-Castell Colour Pencils (Set of 24)", 399, 4.4,
         {"kind": "colour_pencils", "pack_size": 24}, "Break-resistant leads in twenty-four shades."),
        ("Camlin Acrylic Colour Kit", 899, 4.2,
         {"kind": "acrylic", "pack_size": 12}, "Twelve acrylic tubes with brushes and a palette."),
        ("Sketching Pencil Set with Pad", 649, 4.3,
         {"kind": "sketching", "pack_size": 14}, "Graphite grades 8B to 2H with a 100-page pad."),
    ]),

    # ========================================================== GROCERIES
    ("XDAL", "groceries", "pulses", [
        ("Toor Dal 1kg", 179, 4.1,
         {"weight_g": 1000, "kind": "toor"}, "Machine-cleaned split pigeon peas."),
        ("Organic Moong Dal 1kg", 249, 4.3,
         {"weight_g": 1000, "kind": "moong"}, "Certified organic split green gram."),
    ]),
    ("XSPIC", "groceries", "spices", [
        ("Everest Turmeric Powder 500g", 199, 4.2,
         {"weight_g": 500, "kind": "turmeric"}, "Ground turmeric with 3 percent curcumin."),
        ("MDH Garam Masala 100g", 149, 4.3,
         {"weight_g": 100, "kind": "garam_masala"}, "Blended whole spices, ground fresh."),
        ("Organic Whole Spice Box", 899, 4.5,
         {"weight_g": 700, "kind": "assorted"}, "Seven organic whole spices in a steel masala dabba."),
    ]),
    ("XCOFF", "groceries", "coffee", [
        ("Nescafe Classic Instant Coffee 200g", 549, 4.2,
         {"weight_g": 200, "kind": "instant"}, "Freeze-dried instant coffee granules."),
        ("Blue Tokai Arabica Whole Beans 250g", 649, 4.6,
         {"weight_g": 250, "kind": "whole_bean"}, "Single-estate arabica, roasted to order."),
        ("Davidoff Rich Aroma Coffee 100g", 799, 4.4,
         {"weight_g": 100, "kind": "instant"}, "Fine instant coffee with a full aroma."),
    ]),
    ("XATTA", "groceries", "atta and flour", [
        ("Aashirvaad Whole Wheat Atta 5kg", 299, 4.3,
         {"weight_g": 5000, "kind": "whole_wheat"}, "Stone-ground whole wheat atta with the bran retained."),
        ("Organic Multigrain Atta 2kg", 349, 4.2,
         {"weight_g": 2000, "kind": "multigrain"}, "Wheat, jowar, bajra and ragi blend."),
    ]),
    ("XGHEE", "groceries", "ghee", [
        ("Amul Pure Ghee 1L", 649, 4.4,
         {"volume_ml": 1000, "kind": "cow"}, "Made from fresh cream, granular texture."),
        ("A2 Bilona Cow Ghee 500ml", 1299, 4.6,
         {"volume_ml": 500, "kind": "a2_bilona"}, "Hand-churned bilona ghee from A2 milk."),
    ]),
    ("XBISC", "groceries", "biscuits", [
        ("Britannia Marie Gold 1kg", 149, 4.1,
         {"weight_g": 1000, "kind": "marie"}, "Light tea biscuits in a family pack."),
        ("Digestive Oats Biscuits (Pack of 4)", 299, 4.2,
         {"weight_g": 800, "kind": "digestive"}, "Wholewheat and oat biscuits with no added maida."),
    ]),
    ("XPAST", "groceries", "pasta and noodles", [
        ("Durum Wheat Penne Pasta 500g", 149, 4.0,
         {"weight_g": 500, "kind": "penne"}, "Hundred percent durum wheat semolina pasta."),
        ("Whole Wheat Noodles (Pack of 6)", 199, 3.9,
         {"weight_g": 420, "kind": "noodles"}, "Whole wheat instant noodles with a masala sachet."),
    ]),
]


# ---------------------------------------------------------------------
# Third block. Home and personal care exist because a judge typing
# "coffee maker" or "shampoo" should get a coffee maker or a shampoo,
# not the nearest token overlap in a sports catalog.
# ---------------------------------------------------------------------

FAMILIES += [

    # ======================================================= HOME_KITCHEN
    ("XKETL", "home_kitchen", "electric kettle", [
        ("Pigeon Amaze Plus Electric Kettle 1.5L", 799, 4.0,
         {"capacity_l": 1.5, "watt": 1500, "material": "stainless_steel"}, "Stainless kettle with auto shut-off and boil-dry protection."),
        ("Prestige PKOSS Electric Kettle 1.5L", 1299, 4.2,
         {"capacity_l": 1.5, "watt": 1500, "material": "stainless_steel"}, "Concealed element with a cool-touch handle."),
        ("Philips HD9318 Kettle 1.7L", 2499, 4.5,
         {"capacity_l": 1.7, "watt": 2200, "material": "stainless_steel"}, "2200 W rapid boil with a spring-lid and water gauge."),
    ]),
    ("XCOFM", "home_kitchen", "coffee maker", [
        ("Instacuppa French Press 600ml", 899, 4.1,
         {"kind": "french_press", "capacity_ml": 600}, "Borosilicate press with a four-level filtration screen."),
        ("Morphy Richards Drip Coffee Maker", 2999, 4.2,
         {"kind": "drip", "capacity_ml": 600}, "Six-cup drip brewer with a reusable filter and keep-warm plate."),
        ("Agaro Espresso Coffee Machine 20 Bar", 8999, 4.4,
         {"kind": "espresso", "capacity_ml": 1500}, "Twenty-bar pump with a steam wand for milk."),
    ]),
    ("XMIXR", "home_kitchen", "mixer grinder", [
        ("Bajaj Rex 500W Mixer Grinder", 2499, 4.0,
         {"watt": 500, "jars": 3}, "Three stainless jars with a multifunction blade system."),
        ("Preethi Zodiac 750W Mixer Grinder", 6499, 4.5,
         {"watt": 750, "jars": 4}, "Vega W5 motor with a master chef jar for atta kneading."),
    ]),
    ("XCOOK", "home_kitchen", "cookware", [
        ("Non-Stick Tawa 28cm", 649, 4.0,
         {"kind": "tawa", "coating": "non_stick"}, "Three-layer non-stick tawa for rotis and dosas."),
        ("Hawkins Contura Pressure Cooker 3L", 1799, 4.5,
         {"kind": "pressure_cooker", "coating": "none"}, "Hard-anodised 3-litre cooker with a curved base."),
        ("Stainless Steel Cookware Set (5 Piece)", 3499, 4.2,
         {"kind": "set", "coating": "none"}, "Induction-friendly triply set with lids."),
        ("Cast Iron Skillet 25cm", 1499, 4.4,
         {"kind": "skillet", "coating": "seasoned"}, "Pre-seasoned cast iron for searing and oven work."),
    ]),
    ("XSTOR", "home_kitchen", "storage containers", [
        ("Airtight Container Set (Pack of 6)", 899, 4.1,
         {"pack_size": 6, "material": "plastic"}, "BPA-free airtight jars for dry storage."),
        ("Borosilicate Glass Container Set (3)", 1499, 4.4,
         {"pack_size": 3, "material": "glass"}, "Oven-safe glass containers with locking lids."),
    ]),
    ("XLAMP", "home_kitchen", "table lamp", [
        ("LED Study Table Lamp Rechargeable", 799, 4.0,
         {"kind": "led", "rechargeable": True}, "Three brightness levels with a clip base."),
        ("Philips LED Desk Light with Dimmer", 2199, 4.4,
         {"kind": "led", "rechargeable": False}, "Flicker-free light with stepless dimming."),
    ]),
    ("XVACU", "home_kitchen", "vacuum cleaner", [
        ("Eureka Forbes Handheld Vacuum 800W", 2999, 3.9,
         {"watt": 800, "kind": "handheld"}, "Compact handheld vacuum with a blower function."),
        ("Dyson V8 Cordless Vacuum", 29999, 4.6,
         {"watt": 425, "kind": "cordless_stick"}, "Forty minutes of run time with whole-machine filtration."),
    ]),
    ("XIRON", "home_kitchen", "iron", [
        ("Bajaj DX-6 Dry Iron 1000W", 649, 4.0,
         {"watt": 1000, "kind": "dry"}, "Non-stick soleplate with an advanced thermostat."),
        ("Philips Steam Iron 2000W", 1999, 4.4,
         {"watt": 2000, "kind": "steam"}, "Continuous steam with a vertical shot function."),
    ]),
    ("XBEDS", "home_kitchen", "bedsheet", [
        ("Cotton Double Bedsheet with 2 Pillow Covers", 899, 4.0,
         {"size": "double", "fabric": "cotton"}, "144 TC cotton bedsheet, colour-fast."),
        ("400 TC Egyptian Cotton Bedsheet Set", 2999, 4.5,
         {"size": "king", "fabric": "egyptian_cotton"}, "Sateen weave 400 thread count with deep pockets."),
    ]),
    ("XTOWL", "home_kitchen", "towel", [
        ("Cotton Bath Towel (Pack of 2)", 599, 4.0,
         {"pack_size": 2, "gsm": 400}, "400 GSM quick-dry cotton bath towels."),
        ("Egyptian Cotton Bath Towel 600 GSM", 1299, 4.5,
         {"pack_size": 1, "gsm": 600}, "Plush 600 GSM towel with double-stitched hems."),
    ]),
    ("XCHAR", "home_kitchen", "office chair", [
        ("Mesh Back Office Chair", 4999, 3.9,
         {"back": "mesh", "armrest": "fixed"}, "Breathable mesh back with height adjustment."),
        ("Ergonomic Chair with Lumbar Support", 11999, 4.4,
         {"back": "mesh", "armrest": "3d"}, "Adjustable lumbar, headrest and 3D armrests."),
        ("Green Soul Monster Ultimate Gaming Chair", 17999, 4.5,
         {"back": "pu_leather", "armrest": "4d"}, "Recline to 180 degrees with a memory foam pillow set."),
    ]),
    ("XDESKT", "home_kitchen", "study table", [
        ("Foldable Study Table", 2499, 3.9,
         {"material": "engineered_wood", "foldable": True}, "Space-saving folding desk with a laminate top."),
        ("Engineered Wood Study Desk with Shelf", 5999, 4.2,
         {"material": "engineered_wood", "foldable": False}, "Desk with an overhead shelf and cable cutout."),
    ]),

    # ====================================================== PERSONAL_CARE
    ("XSHMP", "personal_care", "shampoo", [
        ("Dove Intense Repair Shampoo 650ml", 549, 4.2,
         {"volume_ml": 650, "hair_type": "damaged"}, "Keratin repair actives for damaged hair."),
        ("Wow Apple Cider Vinegar Shampoo 500ml", 449, 4.0,
         {"volume_ml": 500, "hair_type": "oily"}, "Sulphate-free shampoo with apple cider vinegar."),
        ("Kerastase Bain Satin Shampoo 250ml", 2299, 4.6,
         {"volume_ml": 250, "hair_type": "dry"}, "Salon nourishing shampoo for dry hair."),
    ]),
    ("XFACE", "personal_care", "face wash", [
        ("Himalaya Neem Face Wash 150ml", 199, 4.1,
         {"volume_ml": 150, "skin_type": "oily"}, "Neem and turmeric face wash for acne-prone skin."),
        ("Cetaphil Gentle Skin Cleanser 250ml", 749, 4.6,
         {"volume_ml": 250, "skin_type": "sensitive"}, "Soap-free, fragrance-free cleanser for sensitive skin."),
        ("Minimalist Salicylic Acid Face Wash 100ml", 349, 4.3,
         {"volume_ml": 100, "skin_type": "oily"}, "Two percent salicylic acid with zinc PCA."),
    ]),
    ("XMOIS", "personal_care", "moisturiser", [
        ("Nivea Soft Light Moisturiser 200ml", 299, 4.2,
         {"volume_ml": 200, "skin_type": "normal"}, "Jojoba oil and vitamin E cream that absorbs quickly."),
        ("Cetaphil Moisturising Lotion 250ml", 899, 4.6,
         {"volume_ml": 250, "skin_type": "sensitive"}, "Non-comedogenic lotion for dry, sensitive skin."),
        ("The Ordinary Natural Moisturizing Factors 100ml", 1099, 4.4,
         {"volume_ml": 100, "skin_type": "all"}, "Amino acids and hyaluronic acid in a light cream."),
    ]),
    ("XSUNS", "personal_care", "sunscreen", [
        ("Lakme Sun Expert SPF 50 100ml", 449, 4.0,
         {"spf": 50, "volume_ml": 100}, "Ultra-matte SPF 50 PA+++ lotion."),
        ("Minimalist SPF 50 Sunscreen 50g", 549, 4.5,
         {"spf": 50, "volume_ml": 50}, "Broad-spectrum SPF 50 PA++++ with no white cast."),
        ("La Shield SPF 40 Gel 50g", 899, 4.4,
         {"spf": 40, "volume_ml": 50}, "Dermatologist-recommended gel sunscreen for oily skin."),
    ]),
    ("XTRIM", "personal_care", "trimmer", [
        ("Mi Beard Trimmer 1C", 999, 4.1,
         {"runtime_min": 60, "settings": 20}, "Twenty length settings with a sixty-minute runtime."),
        ("Philips BT3221 Beard Trimmer", 1899, 4.4,
         {"runtime_min": 60, "settings": 20}, "DuraPower with lift-and-trim combs, washable."),
        ("Braun MGK7220 Multi Grooming Kit", 4499, 4.6,
         {"runtime_min": 100, "settings": 39}, "Ten-in-one kit with a Gillette razor and precision heads."),
    ]),
    ("XTOOT", "personal_care", "electric toothbrush", [
        ("Oral-B Vitality 100 Electric Toothbrush", 1499, 4.3,
         {"kind": "rotating", "modes": 1}, "Two-minute timer with a round rotating head."),
        ("Philips Sonicare 2100 Toothbrush", 3499, 4.5,
         {"kind": "sonic", "modes": 1}, "Sonic technology with a pressure sensor and 14-day battery."),
    ]),
    ("XPERF", "personal_care", "perfume", [
        ("Bella Vita Man Eau de Parfum 100ml", 799, 4.1,
         {"volume_ml": 100, "family": "woody"}, "Woody-aromatic eau de parfum with eight-hour longevity."),
        ("Skinn by Titan Raw Perfume 100ml", 1899, 4.3,
         {"volume_ml": 100, "family": "citrus"}, "Citrus opening over a cedar and musk base."),
    ]),
    ("XHAIR", "personal_care", "hair oil", [
        ("Parachute Coconut Hair Oil 500ml", 249, 4.2,
         {"volume_ml": 500, "kind": "coconut"}, "Hundred percent pure coconut oil, cold pressed."),
        ("Indulekha Bringha Hair Oil 100ml", 549, 4.1,
         {"volume_ml": 100, "kind": "ayurvedic"}, "Ayurvedic oil with a selfie comb applicator."),
    ]),
    ("XSOAP", "personal_care", "body wash and soap", [
        ("Dove Cream Beauty Bar (Pack of 4)", 299, 4.4,
         {"pack_size": 4, "kind": "bar"}, "One-quarter moisturising cream in each bar."),
        ("Nivea Lemon Body Wash 750ml", 549, 4.3,
         {"pack_size": 1, "kind": "body_wash"}, "Refreshing lemon body wash with vitamin E."),
    ]),
    ("XDEOD", "personal_care", "deodorant", [
        ("Nivea Fresh Active Deodorant 150ml", 249, 4.2,
         {"volume_ml": 150, "kind": "spray"}, "Forty-eight-hour protection, alcohol free."),
        ("Park Avenue Good Morning Deodorant 150ml", 199, 4.0,
         {"volume_ml": 150, "kind": "spray"}, "Long-lasting fragrance for daily use."),
    ]),
]


def build() -> dict[str, dict]:
    """Deterministic. Same input, same file, every run."""
    out: dict[str, dict] = {}
    for prefix, category, family, variants in FAMILIES:
        skus = [f"{prefix}-{i:03d}" for i in range(1, len(variants) + 1)]
        for idx, (name, rupees, rating, attrs, desc) in enumerate(variants):
            sku = skus[idx]
            # Siblings in the same family, so the cross-sell and comparison
            # engines have real alternatives to reach for.
            siblings = [s for s in skus if s != sku][:3]
            out[sku] = {
                "name": name,
                "category": category,
                "price_paise": rupees * 100,
                "description": desc,
                "rating": rating,
                "attributes": {**attrs, "family": family},
                "compatible_with": siblings,
                "policies": {"return_days": 7 if category != "groceries" else 2,
                             "exchange": category != "groceries"},
                # Deterministic, and varied enough to be worth showing.
                "stock": 4 + (idx * 7 + len(name)) % 37,
            }
    return out


HEADER = '''"""Extended catalog — generated, reviewable, committed.

DO NOT EDIT BY HAND. Regenerate with:

    python scripts/generate_catalog.py

The forty hand-authored SKUs in products.py are the frozen core: their
prices never change and they carry the adversarial injection payloads.
This file is everything else, and it exists because a recommendation
needs alternatives to be a recommendation at all. Before it, asking for
a yoga mat returned a cricket ball, because the catalog held no yoga mat
and the matcher took the closest token overlap it could find.

Products are grouped into families -- one shopping need each -- and every
family spans a real price range with real trade-offs, so a shortlist has
something to weigh. Prices are integer paise. Nothing here is random at
import time.
"""
from __future__ import annotations

from typing import Any

EXTENDED_CATALOG: dict[str, dict[str, Any]] = {
'''

FOOTER = '''}

__all__ = ["EXTENDED_CATALOG"]
'''


def render(catalog: dict[str, dict]) -> str:
    lines = [HEADER]
    current = None
    for sku, item in catalog.items():
        if item["category"] != current:
            current = item["category"]
            lines.append(f"\n    # {'-' * 18} {current.upper()}\n")
        lines.append(f"    {sku!r}: {{\n")
        lines.append(f"        'name': {item['name']!r},\n")
        lines.append(f"        'category': {item['category']!r},\n")
        lines.append(f"        'price_paise': {item['price_paise']},\n")
        lines.append(f"        'description': {item['description']!r},\n")
        lines.append(f"        'rating': {item['rating']},\n")
        lines.append(f"        'attributes': {item['attributes']!r},\n")
        lines.append(f"        'compatible_with': {item['compatible_with']!r},\n")
        lines.append(f"        'policies': {item['policies']!r},\n")
        lines.append(f"        'stock': {item['stock']},\n")
        lines.append("    },\n")
    lines.append(FOOTER)
    return "".join(lines)


def main() -> int:
    catalog = build()
    OUT.write_text(render(catalog), encoding="utf-8")

    by_cat: dict[str, int] = {}
    for item in catalog.values():
        by_cat[item["category"]] = by_cat.get(item["category"], 0) + 1

    print(f"[catalog] wrote {OUT.relative_to(REPO)}")
    print(f"[catalog] {len(catalog)} extended SKUs across {len(by_cat)} categories")
    for cat, n in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print(f"           {cat:14s} {n}")
    print(f"[catalog] {len(FAMILIES)} shopping families")

    subprocess.run([sys.executable, "-m", "ruff", "check", "--fix", str(OUT)],
                   cwd=REPO, capture_output=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
