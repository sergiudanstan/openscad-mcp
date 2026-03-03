// Factory Robot Simulation — Arduino Uno Assembly Line
// Animated with $t (0..1) for a complete SMT assembly cycle
// 10 Phases: PCB entry -> component placement -> reflow -> inspection -> output

// ===================================================================
// SECTION 1: Parameters & Animation Helpers
// ===================================================================

// ---- Factory floor dimensions (mm) ----
floor_length = 600;
floor_width  = 400;

// ---- Conveyor geometry ----
total_length = 400;
belt_width   = 50;
belt_height  = 4;
leg_height   = 40;

// ---- Station X positions along conveyor ----
feeder_x     = -120;
scara_x      = -60;
artic_x      = 40;
oven_entry_x = 120;
oven_exit_x  = 200;
aoi_x        = 240;
output_x     = 300;

// ---- Arduino Uno PCB dimensions ----
pcb_length = 68.6;
pcb_width  = 53.4;
pcb_height = 1.6;

// ---- Color palette (25+ named colors) ----
pcb_green      = [0.05, 0.45, 0.15];
copper_gold    = [0.80, 0.68, 0.20];
ic_black       = [0.10, 0.10, 0.12];
usb_silver     = [0.75, 0.75, 0.78];
cap_tan        = [0.82, 0.72, 0.55];
led_green      = [0.10, 0.95, 0.20];
led_yellow     = [0.95, 0.90, 0.10];
led_orange     = [0.95, 0.55, 0.10];
resistor_dark  = [0.15, 0.12, 0.10];
header_black   = [0.08, 0.08, 0.10];
crystal_silver = [0.80, 0.80, 0.85];
barrel_black   = [0.12, 0.12, 0.14];
robot1_blue    = [0.20, 0.45, 0.85];
robot1_accent  = [0.30, 0.60, 0.95];
robot2_orange  = [0.90, 0.45, 0.15];
robot2_accent  = [0.95, 0.60, 0.25];
agv_teal       = [0.15, 0.55, 0.60];
frame_gray     = [0.35, 0.35, 0.40];
belt_dark      = [0.15, 0.15, 0.18];
roller_silver  = [0.55, 0.57, 0.60];
floor_gray     = [0.28, 0.28, 0.30];
grid_line      = [0.33, 0.33, 0.36];
safety_yellow  = [0.95, 0.85, 0.10];
fence_clear    = [0.70, 0.70, 0.72, 0.3];
oven_red       = [0.85, 0.20, 0.15];
oven_orange    = [0.95, 0.60, 0.15];
hud_bg         = [0.10, 0.10, 0.15];
hud_text       = [0.00, 0.90, 1.00];
hud_green      = [0.20, 1.00, 0.30];
hud_warn       = [1.00, 0.85, 0.00];
worker_skin    = [0.85, 0.70, 0.55];
vest_orange    = [0.95, 0.50, 0.10];
vest_green     = [0.20, 0.75, 0.30];
hat_yellow     = [0.95, 0.85, 0.15];
hat_white      = [0.92, 0.92, 0.92];

// ---- Animation helpers (smoothstep interpolation) ----
function smooth(t)      = t * t * (3 - 2 * t);
function clamp01(t)     = min(1, max(0, t));
function phase(t, a, b) = smooth(clamp01((t - a) / (b - a)));
function lerp(a, b, t)  = a + (b - a) * t;
function lerp3(a, b, t) = [lerp(a[0], b[0], t),
                            lerp(a[1], b[1], t),
                            lerp(a[2], b[2], t)];

// ---- Master timeline (10 phases) ----
//  Phase  1 (0.00-0.08): PCB enters on conveyor from left
//  Phase  2 (0.08-0.18): Robot 1 picks ATmega328P from feeder, places on PCB
//  Phase  3 (0.18-0.28): Robot 1 picks crystal oscillator, places on PCB
//  Phase  4 (0.28-0.38): Robot 2 picks USB-B connector, places on PCB
//  Phase  5 (0.38-0.48): Robot 2 picks capacitors (batch), places on PCB
//  Phase  6 (0.48-0.55): Robot 1 picks voltage regulator, places on PCB
//  Phase  7 (0.55-0.62): Robot 2 picks pin headers, places on PCB
//  Phase  8 (0.62-0.72): Conveyor moves PCB into reflow oven
//  Phase  9 (0.72-0.82): PCB exits oven, AOI camera scans board
//  Phase 10 (0.82-1.00): AGV picks up finished board, drives to output

// Components placed: returns 0-7 based on current animation phase
function components_placed(t) =
        t < 0.08 ? 0     // no components yet
      : t < 0.18 ? 0     // ATmega being placed (not yet seated)
      : t < 0.28 ? 1     // ATmega seated, crystal being placed
      : t < 0.38 ? 2     // crystal seated, USB being placed
      : t < 0.48 ? 3     // USB seated, caps being placed
      : t < 0.55 ? 4     // caps seated, vreg being placed
      : t < 0.62 ? 5     // vreg seated, headers being placed
      : t < 0.72 ? 6     // headers seated, entering oven
      : 7;                // all components soldered (post-reflow)

// PCB x-position along conveyor over time
function pcb_x(t) =
        // Phase 1: enter from left to first station
        t < 0.08 ? lerp(-total_length/2, scara_x, phase(t, 0.00, 0.08))
        // Phases 2-3: stationary at SCARA robot station
      : t < 0.28 ? scara_x
        // Phase 4 transition: slide to articulated robot station
      : t < 0.30 ? lerp(scara_x, artic_x, phase(t, 0.28, 0.30))
        // Phases 4-7: stationary at articulated robot station
      : t < 0.62 ? artic_x
        // Phase 8: conveyor moves PCB into reflow oven
      : t < 0.72 ? lerp(artic_x, oven_exit_x, phase(t, 0.62, 0.72))
        // Phase 9: exit oven, move to AOI
      : t < 0.82 ? lerp(oven_exit_x, aoi_x, phase(t, 0.72, 0.82))
        // Phase 10: AGV picks up from AOI, drives to output
      : lerp(aoi_x, output_x, phase(t, 0.82, 1.00));


// ===================================================================
// SECTION 2: Arduino Uno PCB Model
// ===================================================================

module arduino_pcb(n_components) {
        corner_r = 2;
        // Inset corner cylinder centers from PCB edges
        cx = pcb_length / 2 - corner_r;
        cy = pcb_width  / 2 - corner_r;

        // Mounting hole positions (relative to center)
        hole_positions = [
                [-cx + 2, -cy + 2],
                [ cx - 2, -cy + 2],
                [-cx + 2,  cy - 2],
                [ cx - 2,  cy - 2]
        ];

        // ------ PCB substrate (always visible) ------
        color(pcb_green)
        difference() {
                // Rounded rectangle via hull of 4 corner cylinders
                hull() {
                        translate([-cx, -cy, 0])
                                cylinder(h=pcb_height, r=corner_r, $fn=24);
                        translate([ cx, -cy, 0])
                                cylinder(h=pcb_height, r=corner_r, $fn=24);
                        translate([-cx,  cy, 0])
                                cylinder(h=pcb_height, r=corner_r, $fn=24);
                        translate([ cx,  cy, 0])
                                cylinder(h=pcb_height, r=corner_r, $fn=24);
                }
                // Subtract 4 mounting holes
                for (hp = hole_positions)
                        translate([hp[0], hp[1], -0.1])
                                cylinder(h=pcb_height + 0.2, r=1.5, $fn=16);
        }

        // ------ Copper traces on top surface ------
        color(copper_gold) {
                // Main power bus (horizontal)
                translate([0, -pcb_width/2 + 8, pcb_height])
                        cube([pcb_length - 12, 0.6, 0.1], center=true);
                // Ground bus (horizontal)
                translate([0, -pcb_width/2 + 5, pcb_height])
                        cube([pcb_length - 12, 0.6, 0.1], center=true);
                // Data bus from ATmega to headers
                translate([8, 0, pcb_height])
                        cube([40, 0.5, 0.1], center=true);
                // Crystal trace pair
                translate([-2, 6, pcb_height])
                        cube([18, 0.4, 0.1], center=true);
                // USB data lines
                translate([-24, -4, pcb_height])
                        cube([15, 0.4, 0.1], center=true);
        }

        // ------ Silkscreen text ------
        color([0.90, 0.90, 0.92])
                translate([-14, pcb_width/2 - 10, pcb_height + 0.05])
                        linear_extrude(0.1)
                                text("ARDUINO UNO", size=3.5,
                                     halign="center", valign="center",
                                     font="Liberation Sans:style=Bold");
        color([0.90, 0.90, 0.92])
                translate([-14, pcb_width/2 - 15, pcb_height + 0.05])
                        linear_extrude(0.1)
                                text("R3", size=2.5,
                                     halign="center", valign="center",
                                     font="Liberation Sans:style=Bold");

        // ------ Mounting hole rings (copper annular rings) ------
        color(copper_gold)
                for (hp = hole_positions)
                        translate([hp[0], hp[1], pcb_height])
                                difference() {
                                        cylinder(h=0.1, r=2.5, $fn=16);
                                        translate([0, 0, -0.05])
                                                cylinder(h=0.2, r=1.5, $fn=16);
                                }

        // =====================================================
        // Component 1 - ATmega328P (28-pin DIP)
        // =====================================================
        if (n_components >= 1) {
                translate([8, 2, pcb_height]) {
                        // IC body
                        color(ic_black)
                                translate([0, 0, 1.5])
                                        cube([34, 8, 3], center=true);
                        // Pin 1 dot marker
                        color([0.85, 0.85, 0.85])
                                translate([-15, -2.5, 3.05])
                                        cylinder(h=0.15, r=0.8, $fn=12);
                        // Notch at pin 1 end
                        color([0.20, 0.20, 0.22])
                                translate([-17, 0, 3.05])
                                        cylinder(h=0.15, r=1.2, $fn=16);
                        // Pin rows: 14 pins on each side
                        color(usb_silver)
                                for (i = [0:13]) {
                                        // Bottom row
                                        translate([-15.5 + i * 2.54, -5, 0.4])
                                                cube([0.5, 2.5, 0.8], center=true);
                                        // Top row
                                        translate([-15.5 + i * 2.54,  5, 0.4])
                                                cube([0.5, 2.5, 0.8], center=true);
                                }
                        // IC label text
                        color([0.65, 0.65, 0.65])
                                translate([0, 0, 3.15])
                                        linear_extrude(0.05)
                                                text("ATmega328P", size=1.8,
                                                     halign="center", valign="center",
                                                     font="Liberation Mono:style=Bold");
                }
        }

        // =====================================================
        // Component 2 - Crystal Oscillator (16 MHz)
        // =====================================================
        if (n_components >= 2) {
                translate([-6, 6, pcb_height]) {
                        // Metal can
                        color(crystal_silver)
                                cylinder(h=3, r=2.5, $fn=20);
                        // Top marking
                        color([0.65, 0.65, 0.70])
                                translate([0, 0, 3.0])
                                        cylinder(h=0.15, r=2.3, $fn=20);
                        // Two pins underneath
                        color(usb_silver) {
                                translate([-1.2, 0, -0.5])
                                        cylinder(h=1, r=0.3, $fn=8);
                                translate([ 1.2, 0, -0.5])
                                        cylinder(h=1, r=0.3, $fn=8);
                        }
                        // Frequency label
                        color([0.40, 0.40, 0.45])
                                translate([0, 0, 3.2])
                                        linear_extrude(0.05)
                                                text("16M", size=1.4,
                                                     halign="center", valign="center",
                                                     font="Liberation Mono");
                }
        }

        // =====================================================
        // Component 3 - USB-B Connector
        // =====================================================
        if (n_components >= 3) {
                translate([-pcb_length/2 + 6, 0, pcb_height]) {
                        // Metal housing
                        color(usb_silver)
                        difference() {
                                cube([12, 12, 11], center=false);
                                // Front opening
                                translate([12 - 2, 2, 2])
                                        cube([3, 8, 7], center=false);
                        }
                        // Inner plastic insert (visible through opening)
                        color([0.20, 0.20, 0.22])
                                translate([9, 3, 3])
                                        cube([1, 6, 5], center=false);
                        // Shield tabs on sides
                        color([0.70, 0.70, 0.73]) {
                                translate([0, -0.5, 2])
                                        cube([12, 0.5, 7], center=false);
                                translate([0, 12.0, 2])
                                        cube([12, 0.5, 7], center=false);
                        }
                        // Solder legs
                        color(usb_silver) {
                                translate([2, -1.5, -0.5])
                                        cube([1, 1.5, 1.5]);
                                translate([2, 12.0, -0.5])
                                        cube([1, 1.5, 1.5]);
                                translate([9, -1.5, -0.5])
                                        cube([1, 1.5, 1.5]);
                                translate([9, 12.0, -0.5])
                                        cube([1, 1.5, 1.5]);
                        }
                }
        }

        // =====================================================
        // Component 4 - Capacitors (electrolytic + ceramic)
        // =====================================================
        if (n_components >= 4) {
                // 2x electrolytic capacitors (near power section)
                for (ci = [0:1]) {
                        translate([-18 + ci * 10, -14, pcb_height]) {
                                // Silver aluminum body
                                color(usb_silver)
                                        cylinder(h=8, r=3, $fn=20);
                                // Black band (polarity marker)
                                color(ic_black)
                                        translate([0, 0, 6])
                                                cylinder(h=2.2, r=3.05, $fn=20);
                                // Top cross scoring
                                color([0.65, 0.65, 0.68]) {
                                        translate([0, 0, 8.0])
                                                cube([5.5, 0.4, 0.15], center=true);
                                        translate([0, 0, 8.0])
                                                cube([0.4, 5.5, 0.15], center=true);
                                }
                                // Legs
                                color(usb_silver) {
                                        translate([-1, 0, -0.5])
                                                cylinder(h=1, r=0.25, $fn=6);
                                        translate([ 1, 0, -0.5])
                                                cylinder(h=1, r=0.25, $fn=6);
                                }
                        }
                }
                // 3x ceramic SMD capacitors
                for (ci = [0:2]) {
                        translate([16 + ci * 5, -10, pcb_height]) {
                                color(cap_tan)
                                        cube([3, 2, 1], center=true);
                                // End terminations
                                color(usb_silver) {
                                        translate([-1.3, 0, 0])
                                                cube([0.5, 2, 1], center=true);
                                        translate([ 1.3, 0, 0])
                                                cube([0.5, 2, 1], center=true);
                                }
                        }
                }
        }

        // =====================================================
        // Component 5 - Voltage Regulator (AMS1117 TO-223)
        // =====================================================
        if (n_components >= 5) {
                translate([-20, -20, pcb_height]) {
                        // IC body
                        color(ic_black)
                                translate([0, 0, 1])
                                        cube([6, 4, 2], center=true);
                        // Heatsink tab (silver, extends from one side)
                        color(usb_silver)
                                translate([0, -3, 0.8])
                                        cube([5, 3, 1.6], center=true);
                        // Three pins
                        color(usb_silver)
                                for (pi = [-1:1])
                                        translate([pi * 2, 3, 0.3])
                                                cube([0.6, 1.5, 0.6], center=true);
                        // Label
                        color([0.65, 0.65, 0.65])
                                translate([0, 0, 2.1])
                                        linear_extrude(0.05)
                                                text("1117", size=1.2,
                                                     halign="center", valign="center",
                                                     font="Liberation Mono");
                }
        }

        // =====================================================
        // Component 6 - Pin Headers
        // =====================================================
        if (n_components >= 6) {
                // 8-pin female header (digital pins, top edge)
                translate([12, pcb_width/2 - 4, pcb_height]) {
                        color(header_black)
                                cube([20.5, 2.5, 8.5], center=true);
                        // Pin openings
                        color([0.15, 0.15, 0.17])
                                for (pi = [0:7])
                                        translate([-8.89 + pi * 2.54, 0, 4.5])
                                                cube([1.2, 1.2, 1], center=true);
                        // Solder pins below
                        color(usb_silver)
                                for (pi = [0:7])
                                        translate([-8.89 + pi * 2.54, 0, -5])
                                                cube([0.5, 0.5, 3], center=true);
                }
                // 6-pin female header (analog pins, bottom edge)
                translate([12, -pcb_width/2 + 4, pcb_height]) {
                        color(header_black)
                                cube([15.5, 2.5, 8.5], center=true);
                        // Pin openings
                        color([0.15, 0.15, 0.17])
                                for (pi = [0:5])
                                        translate([-6.35 + pi * 2.54, 0, 4.5])
                                                cube([1.2, 1.2, 1], center=true);
                        // Solder pins below
                        color(usb_silver)
                                for (pi = [0:5])
                                        translate([-6.35 + pi * 2.54, 0, -5])
                                                cube([0.5, 0.5, 3], center=true);
                }
                // ICSP 2x3 header (near ATmega)
                translate([24, 8, pcb_height]) {
                        color(header_black)
                                cube([5.2, 7.8, 8.5], center=true);
                        // 6 pin openings (2x3 grid)
                        color([0.15, 0.15, 0.17])
                                for (r = [0:1])
                                        for (c = [0:2])
                                                translate([-1.27 + r * 2.54,
                                                           -2.54 + c * 2.54,
                                                           4.5])
                                                        cube([1.2, 1.2, 1], center=true);
                }
        }

        // =====================================================
        // Component 7 - Final details (post-reflow)
        // =====================================================
        if (n_components >= 7) {
                // DC barrel jack
                translate([-pcb_length/2 + 4, -pcb_width/2 + 6, pcb_height]) {
                        color(barrel_black) {
                                cube([9, 9, 10], center=false);
                                // Barrel opening
                                translate([9, 4.5, 5])
                                        rotate([0, 90, 0])
                                                cylinder(h=2, r=3.2, $fn=16);
                        }
                        // Center pin (visible in opening)
                        color(copper_gold)
                                translate([10.5, 4.5, 5])
                                        rotate([0, 90, 0])
                                                cylinder(h=1, r=1, $fn=12);
                }

                // Reset button
                translate([4, -18, pcb_height]) {
                        // Metal body
                        color([0.70, 0.70, 0.73])
                                cube([6, 6, 2.5], center=true);
                        // Button cap
                        color(usb_silver)
                                translate([0, 0, 1.5])
                                        cylinder(h=1, r=1.5, $fn=12);
                        // Four legs
                        color(usb_silver)
                                for (dx = [-1, 1])
                                        for (dy = [-1, 1])
                                                translate([dx * 3.5, dy * 3.5, -0.5])
                                                        cube([0.6, 0.6, 1.5], center=true);
                }

                // LEDs (4 tiny domes with labels)
                // Power LED (green)
                translate([-10, -20, pcb_height]) {
                        color(led_green, alpha=0.85)
                                sphere(r=1, $fn=12);
                        color([0.85, 0.85, 0.85])
                                translate([0, -2.5, 0])
                                        linear_extrude(0.05)
                                                text("ON", size=1.2,
                                                     halign="center",
                                                     font="Liberation Mono");
                }
                // TX LED (yellow)
                translate([-6, -20, pcb_height]) {
                        color(led_yellow, alpha=0.85)
                                sphere(r=1, $fn=12);
                        color([0.85, 0.85, 0.85])
                                translate([0, -2.5, 0])
                                        linear_extrude(0.05)
                                                text("TX", size=1.2,
                                                     halign="center",
                                                     font="Liberation Mono");
                }
                // RX LED (green)
                translate([-2, -20, pcb_height]) {
                        color(led_green, alpha=0.85)
                                sphere(r=1, $fn=12);
                        color([0.85, 0.85, 0.85])
                                translate([0, -2.5, 0])
                                        linear_extrude(0.05)
                                                text("RX", size=1.2,
                                                     halign="center",
                                                     font="Liberation Mono");
                }
                // Pin 13 LED (orange)
                translate([2, -20, pcb_height]) {
                        color(led_orange, alpha=0.85)
                                sphere(r=1, $fn=12);
                        color([0.85, 0.85, 0.85])
                                translate([0, -2.5, 0])
                                        linear_extrude(0.05)
                                                text("L", size=1.2,
                                                     halign="center",
                                                     font="Liberation Mono");
                }

                // 4x SMD resistors near LEDs
                color(resistor_dark)
                        for (ri = [0:3])
                                translate([-10 + ri * 4, -16, pcb_height]) {
                                        cube([2.0, 1.2, 0.6], center=true);
                                        // End terminations
                                        color(usb_silver) {
                                                translate([-0.8, 0, 0])
                                                        cube([0.4, 1.2, 0.6], center=true);
                                                translate([ 0.8, 0, 0])
                                                        cube([0.4, 1.2, 0.6], center=true);
                                        }
                                }

                // Power LED glow effect (translucent green sphere)
                color([0.10, 0.95, 0.20, 0.25])
                        translate([-10, -20, pcb_height + 1])
                                sphere(r=3.5, $fn=16);
        }
}

// ===================================================================
// End of Section 1-2
// ===================================================================
// ============================================================
// Section 3: Component Feeders
// Section 4: SCARA Robot (Robot 1)
// ============================================================
// NOTE: smooth(), clamp01(), phase(), lerp() are defined in
// Section 1. Do NOT redefine them here.
// ============================================================

// ========== SECTION 3: COMPONENT FEEDER STATION ==========

module component_feeder_station(n_placed) {
        feeder_label_color = [0.90, 0.90, 0.92];
        label_bg_color = [0.20, 0.20, 0.25];

        // --- Tape Reel Feeder 1 (capacitors/resistors) ---
        translate([0, 0, 0]) {
                // Reel body
                color([0.55, 0.55, 0.58])
                        cylinder(r=25, h=8, $fn=48);
                // Axle through center
                color([0.70, 0.70, 0.72])
                        translate([0, 0, -1])
                                cylinder(r=3, h=10, $fn=16);
                // Hub cap
                color([0.40, 0.40, 0.42])
                        translate([0, 0, 8])
                                cylinder(r=8, h=1, $fn=24);
                // Tape strip extending toward conveyor
                color([0.85, 0.80, 0.65])
                        translate([25, -2, 3])
                                cube([40, 4, 0.5]);
                // Components on tape (tan/dark resistors)
                for (i = [0:5]) {
                        comp_color = (i % 2 == 0) ? [0.75, 0.65, 0.45] : [0.30, 0.25, 0.20];
                        color(comp_color)
                                translate([30 + i * 6, -0.5, 3.5])
                                        cube([3, 1.5, 1.2]);
                }
                // Label
                color(label_bg_color)
                        translate([0, -28, 0.2])
                                cube([40, 8, 0.3], center=true);
                color(feeder_label_color)
                        translate([0, -28, 0.5])
                                text("FEEDER 1", size=4, halign="center", valign="center",
                                        font="Liberation Sans:style=Bold");
        }

        // --- Tape Reel Feeder 2 (depletes after n_placed >= 4) ---
        translate([0, 60, 0]) {
                // Reel body
                color([0.50, 0.50, 0.55])
                        cylinder(r=25, h=8, $fn=48);
                // Axle
                color([0.70, 0.70, 0.72])
                        translate([0, 0, -1])
                                cylinder(r=3, h=10, $fn=16);
                // Hub cap
                color([0.40, 0.40, 0.42])
                        translate([0, 0, 8])
                                cylinder(r=8, h=1, $fn=24);
                // Tape strip
                color([0.80, 0.75, 0.60])
                        translate([25, -2, 3])
                                cube([40, 4, 0.5]);
                // Components on tape (only visible if not depleted)
                if (n_placed < 4) {
                        for (i = [0:4]) {
                                color([0.25, 0.50, 0.75])
                                        translate([30 + i * 6, -0.5, 3.5])
                                                cube([3, 1.5, 1.2]);
                        }
                }
                // Label
                color(label_bg_color)
                        translate([0, -28, 0.2])
                                cube([40, 8, 0.3], center=true);
                color(feeder_label_color)
                        translate([0, -28, 0.5])
                                text("FEEDER 2", size=4, halign="center", valign="center",
                                        font="Liberation Sans:style=Bold");
        }

        // --- Tray Feeder (ATmega ICs, depletes after n_placed >= 1) ---
        translate([80, 0, 0]) {
                // Tray base
                color([0.45, 0.45, 0.48])
                        cube([40, 30, 3]);
                // Raised edge walls
                color([0.50, 0.50, 0.53]) {
                        // Front wall
                        translate([0, 0, 3])
                                cube([40, 1.5, 4]);
                        // Back wall
                        translate([0, 28.5, 3])
                                cube([40, 1.5, 4]);
                        // Left wall
                        translate([0, 0, 3])
                                cube([1.5, 30, 4]);
                        // Right wall
                        translate([38.5, 0, 3])
                                cube([1.5, 30, 4]);
                }
                // 4x4 grid of IC slots
                for (row = [0:3]) {
                        for (col = [0:3]) {
                                slot_idx = row * 4 + col;
                                // Show IC only if slot not emptied
                                if (slot_idx >= n_placed) {
                                        color([0.10, 0.10, 0.12])
                                                translate([5 + col * 9, 4 + row * 6.5, 3])
                                                        cube([7, 4, 1.5]);
                                        // IC pins (tiny silver marks)
                                        color([0.75, 0.75, 0.78]) {
                                                translate([5 + col * 9, 3.5 + row * 6.5, 3])
                                                        cube([7, 0.4, 0.3]);
                                                translate([5 + col * 9, 8.5 + row * 6.5, 3])
                                                        cube([7, 0.4, 0.3]);
                                        }
                                }
                        }
                }
                // Label
                color(label_bg_color)
                        translate([20, -8, 0.2])
                                cube([40, 8, 0.3], center=true);
                color(feeder_label_color)
                        translate([20, -8, 0.5])
                                text("FEEDER 3", size=4, halign="center", valign="center",
                                        font="Liberation Sans:style=Bold");
        }

        // --- Tube Feeder (pin headers, depletes after n_placed >= 6) ---
        translate([80, 60, 0]) {
                // Magazine tube angled at 15 degrees
                rotate([0, -15, 0]) {
                        color([0.60, 0.60, 0.62])
                                cube([60, 8, 8]);
                        // Open end cap
                        color([0.50, 0.50, 0.52])
                                translate([0, 0, 0])
                                        cube([2, 8, 8]);
                        // Pin headers inside (dark strips)
                        if (n_placed < 6) {
                                for (i = [0:4]) {
                                        color([0.15, 0.15, 0.18])
                                                translate([5 + i * 10, 2, 2])
                                                        cube([8, 4, 4]);
                                }
                        }
                }
                // Label
                color(label_bg_color)
                        translate([30, -8, 0.2])
                                cube([40, 8, 0.3], center=true);
                color(feeder_label_color)
                        translate([30, -8, 0.5])
                                text("FEEDER 4", size=4, halign="center", valign="center",
                                        font="Liberation Sans:style=Bold");
        }

        // --- Bulk Bowl Feeder (USB-B connectors, depletes after n_placed >= 3) ---
        translate([45, 120, 0]) {
                // Bowl body (outer cylinder minus inner)
                color([0.55, 0.58, 0.55]) {
                        difference() {
                                cylinder(r=20, h=15, $fn=48);
                                translate([0, 0, 3])
                                        cylinder(r=17, h=13, $fn=48);
                        }
                }
                // USB-B connectors inside bowl
                if (n_placed < 3) {
                        for (i = [0:2]) {
                                angle = i * 120;
                                color([0.75, 0.75, 0.78])
                                        translate([8 * cos(angle), 8 * sin(angle), 4])
                                                cube([5, 6, 4], center=true);
                        }
                }
                // Vibration track / spiral ramp from bowl
                color([0.60, 0.62, 0.60]) {
                        for (a = [0:15:270]) {
                                ramp_r = 20 + a / 90 * 5;
                                ramp_z = 3 + a / 270 * 10;
                                translate([ramp_r * cos(a), ramp_r * sin(a), ramp_z])
                                        cube([4, 2, 1.5], center=true);
                        }
                }
                // Track extension toward pickup point
                color([0.60, 0.62, 0.60])
                        translate([25, 0, 13])
                                cube([15, 3, 1.5]);
                // Label
                color(label_bg_color)
                        translate([0, -25, 0.2])
                                cube([40, 8, 0.3], center=true);
                color(feeder_label_color)
                        translate([0, -25, 0.5])
                                text("FEEDER 5", size=4, halign="center", valign="center",
                                        font="Liberation Sans:style=Bold");
        }
}


// ========== SECTION 4: SCARA ROBOT (Robot 1) ==========

// SCARA arm link using hull of two cylinders (same pattern as pick_and_place_arm)
module scara_arm_link(length, width, thick) {
        hull() {
                cylinder(h=thick, r=width/2, center=true, $fn=28);
                translate([length, 0, 0])
                        cylinder(h=thick, r=width/2, center=true, $fn=28);
        }
}

// SCARA joint pin (silver cylinder at revolute joint)
module scara_joint_pin(h) {
        color([0.85, 0.85, 0.88])
                cylinder(h=h, r=4, center=true, $fn=24);
}

// SCARA Robot keyframes: [j1, j2, z, j4, grip]
function scara1_state(t) =
        // Phase 1 (0.00-0.08): Home position, waiting
        t < 0.08 ? [0, -30, 0, 0, 0]
        // Phase 2 (0.08-0.13): Move to feeder (pick ATmega)
        : t < 0.13 ? let(f = phase(t, 0.08, 0.13))
                [lerp(0, -45, f), lerp(-30, -60, f), 0, lerp(0, 10, f), 0]
        // Phase 2b (0.13-0.15): Lower Z, grip
        : t < 0.15 ? let(f = phase(t, 0.13, 0.15))
                [-45, -60, lerp(0, 25, f), 10, f]
        // Phase 2c (0.15-0.18): Lift, move to PCB, place
        : t < 0.18 ? let(f = phase(t, 0.15, 0.18))
                [lerp(-45, 20, f), lerp(-60, -40, f), lerp(25, 0, f), lerp(10, 0, f), 1-f*0.5]
        // Phase 3 (0.18-0.23): Move to feeder (pick crystal)
        : t < 0.23 ? let(f = phase(t, 0.18, 0.23))
                [lerp(20, -40, f), lerp(-40, -55, f), 0, 0, 0]
        // Phase 3b (0.23-0.25): Pick crystal
        : t < 0.25 ? let(f = phase(t, 0.23, 0.25))
                [-40, -55, lerp(0, 25, f), 0, f]
        // Phase 3c (0.25-0.28): Place crystal on PCB
        : t < 0.28 ? let(f = phase(t, 0.25, 0.28))
                [lerp(-40, 15, f), lerp(-55, -35, f), lerp(25, 0, f), 0, 1-f]
        // Return to home (0.28-0.32): SCARA retracts while Robot 2 works
        : t < 0.32 ? let(f = phase(t, 0.28, 0.32))
                [lerp(15, 0, f), lerp(-35, -30, f), 0, 0, 0]
        // Idle while Robot 2 works (0.32-0.48)
        : t < 0.48 ? [0, -30, 0, 0, 0]
        // Phase 6 (0.48-0.51): Move to pick voltage regulator
        : t < 0.51 ? let(f = phase(t, 0.48, 0.51))
                [lerp(0, -35, f), lerp(-30, -50, f), 0, 0, 0]
        // Phase 6b (0.51-0.53): Pick vreg
        : t < 0.53 ? let(f = phase(t, 0.51, 0.53))
                [-35, -50, lerp(0, 25, f), 5, f]
        // Phase 6c (0.53-0.55): Place vreg
        : t < 0.55 ? let(f = phase(t, 0.53, 0.55))
                [lerp(-35, 10, f), lerp(-50, -30, f), lerp(25, 0, f), lerp(5, 0, f), 1-f]
        // Return to home (0.55-0.58)
        : t < 0.58 ? let(f = phase(t, 0.55, 0.58))
                [lerp(10, 0, f), lerp(-30, -30, f), 0, 0, 0]
        // Idle: home position
        : [0, -30, 0, 0, 0];

module scara_robot(j1_angle, j2_angle, z_height, j4_rot, grip_open) {
        robot1_blue = [0.20, 0.45, 0.85];
        robot1_accent = [0.30, 0.60, 0.95];
        dark_gray = [0.25, 0.25, 0.28];
        silver = [0.75, 0.75, 0.78];
        pin_color = [0.85, 0.85, 0.88];

        // --- Base Pedestal ---
        // Lower base (heavy, dark gray)
        color(dark_gray) {
                cylinder(r=30, h=10, $fn=48);
                // 6 mounting bolts around base
                for (a = [0:60:300])
                        rotate([0, 0, a])
                                translate([26, 0, 10])
                                        cylinder(r=2, h=2, $fn=12);
        }
        // Mounting bolt caps (silver)
        color(silver)
                for (a = [0:60:300])
                        rotate([0, 0, a])
                                translate([26, 0, 12])
                                        cylinder(r=1.5, h=1, $fn=12);
        // Upper base column
        color(robot1_blue)
                translate([0, 0, 10])
                        cylinder(r=22, h=25, $fn=48);
        // Status LED (green sphere on base)
        color([0.20, 0.85, 0.30])
                translate([20, 0, 20])
                        sphere(r=1.5, $fn=16);
        // Cable entry at rear
        color([0.35, 0.35, 0.38])
                translate([-22, 0, 8])
                        rotate([0, 90, 0])
                                cylinder(r=3, h=5, $fn=16);

        // --- Joint 1: Base rotation (around Z) ---
        translate([0, 0, 35])
        rotate([0, 0, j1_angle]) {
                // J1 joint housing
                color(robot1_blue)
                        cylinder(r=16, h=8, $fn=36);
                // J1 joint pin
                scara_joint_pin(12);

                // --- Link 1 (Upper arm) ---
                translate([0, 0, 4]) {
                        color(robot1_blue)
                                scara_arm_link(80, 18, 12);
                        // Cable routing channel on top
                        color([0.15, 0.35, 0.70])
                                translate([40, 0, 6.5])
                                        cube([60, 3, 1.5], center=true);
                }

                // --- Joint 2 at end of Link 1 ---
                translate([80, 0, 0]) {
                        // J2 joint housing
                        color(robot1_accent)
                                cylinder(r=12, h=8, $fn=32);
                        // J2 joint pin
                        scara_joint_pin(10);

                        rotate([0, 0, j2_angle]) {
                                // --- Link 2 (Forearm) ---
                                translate([0, 0, 4]) {
                                        color(robot1_accent)
                                                scara_arm_link(60, 14, 10);
                                        // Cable routing channel
                                        color([0.22, 0.48, 0.80])
                                                translate([30, 0, 5.5])
                                                        cube([44, 2.5, 1.2], center=true);
                                }

                                // --- Z-axis (vertical prismatic) at end of Link 2 ---
                                translate([60, 0, 0]) {
                                        // Z-axis housing
                                        color(dark_gray)
                                                translate([0, 0, -5])
                                                        cylinder(r=8, h=15, $fn=28);
                                        // Silver guide rails (2 thin rods)
                                        color(silver) {
                                                translate([6, 0, -5])
                                                        cylinder(r=1.2, h=50, $fn=12);
                                                translate([-6, 0, -5])
                                                        cylinder(r=1.2, h=50, $fn=12);
                                        }

                                        // --- Sliding shaft (moves with z_height) ---
                                        translate([0, 0, -z_height]) {
                                                // Vertical shaft
                                                color(dark_gray)
                                                        translate([0, 0, -20])
                                                                cylinder(r=5, h=20, $fn=24);

                                                // --- J4 rotation at bottom of shaft ---
                                                translate([0, 0, -20])
                                                rotate([0, 0, j4_rot]) {
                                                        // Rotation housing
                                                        color(dark_gray)
                                                                cylinder(r=6, h=4, center=true, $fn=24);

                                                        // --- End-effector (Vacuum nozzle) ---
                                                        // Nozzle body
                                                        color(dark_gray)
                                                                translate([0, 0, -15])
                                                                        cylinder(r=3, h=15, $fn=20);
                                                        // Red accent ring
                                                        color([0.85, 0.20, 0.20])
                                                                translate([0, 0, -8])
                                                                        cylinder(r=3.5, h=1.5, $fn=20);
                                                        // Suction cup at tip (disk)
                                                        suction_r = grip_open > 0.5 ? 4 : 3.5;
                                                        color([0.30, 0.30, 0.32])
                                                                translate([0, 0, -16])
                                                                        cylinder(r=suction_r, h=1.5, $fn=24);
                                                        // Suction cup lip
                                                        color([0.35, 0.35, 0.38])
                                                                translate([0, 0, -16.5]) {
                                                                        difference() {
                                                                                cylinder(r=suction_r + 0.5, h=0.8, $fn=24);
                                                                                translate([0, 0, -0.1])
                                                                                        cylinder(r=suction_r - 1, h=1, $fn=24);
                                                                        }
                                                                }
                                                        // Pneumatic line running up Z-shaft
                                                        color([0.20, 0.20, 0.22])
                                                                translate([3, 0, -7.5])
                                                                        cylinder(r=1, h=30, $fn=10);
                                                }
                                        }
                                }
                        }
                }
        }
}
// =====================================================================
// Section 5: 6-DOF Articulated Robot (Robot 2)
// =====================================================================

// Articulated arm keyframes: [j1, j2, j3, j4, j5, j6, grip]
function arm2_state(t) =
        // Idle until phase 4
        t < 0.28 ? [0, 30, -60, 30, 0, 0, 1]
        // Phase 4 (0.28-0.33): Move to bulk feeder (pick USB-B)
        : t < 0.33 ? let(f = phase(t, 0.28, 0.33))
                [lerp(0, 50, f), lerp(30, 55, f), lerp(-60, -90, f), lerp(30, 35, f), 0, 0, 1]
        // Phase 4b (0.33-0.35): Grip USB-B
        : t < 0.35 ? let(f = phase(t, 0.33, 0.35))
                [50, 55, lerp(-90, -95, f), 35, 0, 0, lerp(1, 0, f)]
        // Phase 4c (0.35-0.38): Place USB-B on PCB
        : t < 0.38 ? let(f = phase(t, 0.35, 0.38))
                [lerp(50, -10, f), lerp(55, 50, f), lerp(-95, -80, f), lerp(35, 30, f), 0, 0, lerp(0, 1, f)]
        // Phase 5 (0.38-0.43): Move to tape feeder (pick caps)
        : t < 0.43 ? let(f = phase(t, 0.38, 0.43))
                [lerp(-10, 40, f), lerp(50, 60, f), lerp(-80, -100, f), lerp(30, 40, f), 0, 0, 1]
        // Phase 5b (0.43-0.45): Grip capacitors
        : t < 0.45 ? let(f = phase(t, 0.43, 0.45))
                [40, 60, lerp(-100, -105, f), 40, 0, 0, lerp(1, 0, f)]
        // Phase 5c (0.45-0.48): Place caps on PCB
        : t < 0.48 ? let(f = phase(t, 0.45, 0.48))
                [lerp(40, -15, f), lerp(60, 45, f), lerp(-105, -75, f), lerp(40, 30, f), 0, 0, lerp(0, 1, f)]
        // Return to idle (0.48-0.52): Arm retracts while SCARA works on phase 6
        : t < 0.52 ? let(f = phase(t, 0.48, 0.52))
                [lerp(-15, 0, f), lerp(45, 30, f), lerp(-75, -60, f), lerp(30, 30, f), 0, 0, 1]
        // Idle while SCARA works (0.52-0.55)
        : t < 0.55 ? [0, 30, -60, 30, 0, 0, 1]
        // Phase 7 (0.55-0.58): Move to tube feeder (pick headers)
        : t < 0.58 ? let(f = phase(t, 0.55, 0.58))
                [lerp(0, 55, f), lerp(30, 50, f), lerp(-60, -85, f), lerp(30, 35, f), 0, 0, 1]
        // Phase 7b (0.58-0.60): Grip headers
        : t < 0.60 ? let(f = phase(t, 0.58, 0.60))
                [55, 50, lerp(-85, -90, f), 35, 0, 0, lerp(1, 0, f)]
        // Phase 7c (0.60-0.62): Place headers on PCB
        : t < 0.62 ? let(f = phase(t, 0.60, 0.62))
                [lerp(55, -5, f), lerp(50, 40, f), lerp(-90, -70, f), lerp(35, 30, f), 0, 0, lerp(0, 1, f)]
        // Return to idle (0.62-0.66)
        : t < 0.66 ? let(f = phase(t, 0.62, 0.66))
                [lerp(-5, 0, f), lerp(40, 30, f), lerp(-70, -60, f), lerp(30, 30, f), 0, 0, 1]
        // Idle
        : [0, 30, -60, 30, 0, 0, 1];

module arm2_link(length, width, thick) {
        hull() {
                cylinder(h=thick, r=width/2, center=true, $fn=28);
                translate([0, 0, length])
                        cylinder(h=thick, r=width/2, center=true, $fn=28);
        }
}

module arm2_joint_pin(h) {
        color([0.85, 0.85, 0.88])
                cylinder(h=h, r=4, center=true, $fn=24);
}

module articulated_robot(j1, j2, j3, j4, j5, j6, grip_open) {
        // --- Colors ---
        robot2_orange = [0.90, 0.45, 0.15];
        robot2_accent = [0.95, 0.60, 0.25];
        base_gray     = [0.30, 0.30, 0.35];
        silver        = [0.75, 0.75, 0.78];
        grip_silver   = [0.70, 0.70, 0.72];
        pin_color     = [0.85, 0.85, 0.88];
        rubber_dark   = [0.20, 0.20, 0.22];

        // --- Geometry ---
        upper_len  = 75;
        upper_w    = 16;
        upper_t    = 14;
        fore_len   = 65;
        fore_w     = 13;
        fore_t     = 12;
        grip_gap   = lerp(4, 20, grip_open);

        // === Base: octagonal pedestal ===
        color(base_gray) {
                cylinder(r=28, h=12, $fn=8);
                // Mounting plate
                translate([0, 0, 12])
                        cylinder(r=18, h=3, $fn=32);
        }
        // Bolt holes around pedestal edge
        color([0.20, 0.20, 0.22])
                for (a = [0 : 45 : 315])
                        rotate([0, 0, a])
                                translate([24, 0, 12.5])
                                        cylinder(r=1.8, h=3.5, center=true, $fn=12);

        // === Kinematic chain ===
        // J1: rotate about vertical Z at base top
        translate([0, 0, 15])
        rotate([0, 0, j1]) {

                // --- Shoulder housing ---
                color(robot2_orange) {
                        translate([0, 0, 0])
                                cube([20, 20, 25], center=true);
                }
                // Shoulder joint pin
                rotate([0, 90, 0])
                        arm2_joint_pin(26);

                // J2: shoulder pitch (rotate X)
                translate([0, 0, 12.5])
                rotate([j2, 0, 0]) {

                        // --- Upper arm ---
                        color(robot2_orange)
                                arm2_link(upper_len, upper_w, upper_t);
                        // Cable channel groove
                        color([0.80, 0.38, 0.12])
                                translate([0, 0, upper_len/2])
                                        cube([3, upper_t + 1, upper_len - 20], center=true);

                        // J3: elbow
                        translate([0, 0, upper_len]) {
                                // Elbow housing
                                color(robot2_accent)
                                        rotate([0, 90, 0])
                                                cylinder(r=10, h=16, center=true, $fn=28);
                                // Elbow joint pin
                                rotate([0, 90, 0])
                                        arm2_joint_pin(20);

                                rotate([j3, 0, 0]) {

                                        // --- Forearm ---
                                        color(robot2_accent)
                                                arm2_link(fore_len, fore_w, fore_t);
                                        // Cable channel
                                        color([0.88, 0.52, 0.20])
                                                translate([0, 0, fore_len/2])
                                                        cube([2.5, fore_t + 1, fore_len - 16], center=true);

                                        // J4: wrist pitch
                                        translate([0, 0, fore_len]) {
                                                // Wrist housing 1
                                                color(silver)
                                                        rotate([0, 90, 0])
                                                                cylinder(r=7, h=14, center=true, $fn=24);
                                                rotate([0, 90, 0])
                                                        arm2_joint_pin(18);

                                                rotate([j4, 0, 0]) {

                                                        // J5: wrist roll
                                                        translate([0, 0, 10]) {
                                                                // Wrist housing 2
                                                                color(silver)
                                                                        cylinder(r=7, h=10, center=true, $fn=24);

                                                                rotate([0, 0, j5]) {

                                                                        // J6: end rotation (unused)
                                                                        translate([0, 0, 5])
                                                                        rotate([j6, 0, 0]) {

                                                                                // === Gripper (parallel jaw) ===
                                                                                // Gripper body
                                                                                color(grip_silver)
                                                                                        cube([25, 14, 8], center=true);

                                                                                // Left finger
                                                                                translate([-grip_gap/2, 0, -4]) {
                                                                                        color(grip_silver)
                                                                                                cube([4, 10, 25], center=true);
                                                                                        // Rubber pad
                                                                                        color(rubber_dark)
                                                                                                translate([2, 0, -10])
                                                                                                        cube([2, 8, 6], center=true);
                                                                                }

                                                                                // Right finger
                                                                                translate([grip_gap/2, 0, -4]) {
                                                                                        color(grip_silver)
                                                                                                cube([4, 10, 25], center=true);
                                                                                        // Rubber pad
                                                                                        color(rubber_dark)
                                                                                                translate([-2, 0, -10])
                                                                                                        cube([2, 8, 6], center=true);
                                                                                }

                                                                        } // end J6
                                                                } // end J5
                                                        } // end wrist roll housing
                                                } // end J4
                                        } // end wrist pitch
                                } // end J3
                        } // end elbow
                } // end J2
        } // end J1
}


// =====================================================================
// Section 6: Conveyor System
// =====================================================================

module pcb_carrier(x_pos) {
        // Flat aluminum carrier plate (slightly larger than PCB)
        translate([x_pos, 0, 0]) {
                // Base plate
                color([0.60, 0.60, 0.62])
                        cube([75, 60, 2], center=true);
                // Registration pins (4 corners)
                color([0.50, 0.50, 0.55])
                        for (cx = [-32, 32])
                                for (cy = [-25, 25])
                                        translate([cx, cy, 2])
                                                cylinder(r=1.5, h=4, $fn=12);
        }
}

module conveyor_belt(length, width, t_anim) {
        // --- Colors ---
        belt_dark    = [0.15, 0.15, 0.18];
        roller_silver = [0.55, 0.57, 0.60];
        frame_gray   = [0.35, 0.35, 0.40];

        // --- Geometry ---
        belt_height = 4;
        leg_height  = 40;
        n_rollers   = 12;

        // === Support frame ===
        color(frame_gray) {
                // Side rails
                for (s = [-1, 1])
                        translate([0, s * (width/2 + 3), leg_height + belt_height/2])
                                cube([length + 10, 4, 8], center=true);

                // 6 pairs of legs
                for (lx_frac = [0 : 5]) {
                        lx = -length/2 + length/5 * lx_frac;
                        for (s = [-1, 1]) {
                                // Vertical leg
                                translate([lx, s * (width/2 + 3), leg_height/2])
                                        cube([6, 6, leg_height], center=true);
                        }
                        // Cross brace between legs
                        translate([lx, 0, 10])
                                cube([4, width + 10, 4], center=true);
                }
        }

        // === Belt surface ===
        color(belt_dark)
                translate([0, 0, leg_height + belt_height/2])
                        cube([length, width, belt_height], center=true);

        // Animated segment lines (moving with t_anim)
        seg_offset = (t_anim % 0.1) / 0.1 * 12;
        color([0.22, 0.22, 0.25])
                for (sx = [-length/2 + seg_offset : 12 : length/2])
                        translate([sx, 0, leg_height + belt_height + 0.2])
                                cube([1.5, width - 2, 0.3], center=true);

        // === End rollers ===
        color(roller_silver)
                for (ex = [-1, 1])
                        translate([ex * length/2, 0, leg_height + belt_height/2])
                                rotate([90, 0, 0])
                                        cylinder(h=width + 8, r=6, center=true, $fn=24);

        // === Intermediate rollers (below belt) ===
        color([0.50, 0.50, 0.53])
                for (rx = [-length/2 + 25 : length/(n_rollers + 1) : length/2 - 25])
                        translate([rx, 0, leg_height - 2])
                                rotate([90, 0, 0])
                                        cylinder(h=width + 2, r=3, center=true, $fn=16);

        // === Side guide rails (above belt surface) ===
        color([0.45, 0.45, 0.50])
                for (s = [-1, 1])
                        translate([0, s * (width/2 - 2), leg_height + belt_height + 5])
                                cube([length - 10, 2, 10], center=true);
}
// =====================================================================
// Section 7: Reflow Solder Oven
// Section 8: AOI Inspection Station
// Section 9: AGV Transport Robot
// =====================================================================

// ========== SECTION 7: REFLOW SOLDER OVEN ==========

module reflow_oven(pcb_inside, progress) {
        oven_body = [0.55, 0.55, 0.58];
        oven_top = [0.50, 0.50, 0.53];
        oven_dark = [0.30, 0.30, 0.33];

        // --- Main housing ---
        color(oven_body)
                cube([80, 70, 50], center=true);
        // Recessed top panel
        color(oven_top)
                translate([0, 0, 25.5])
                        cube([76, 66, 2], center=true);

        // --- Side vents (thin horizontal slots) ---
        color(oven_dark)
                for (s = [-1, 1])
                        for (vi = [0:3])
                                translate([0, s * 36, -10 + vi * 8])
                                        cube([60, 1, 2], center=true);

        // --- Entry and exit openings ---
        color(oven_dark)
                translate([-40.5, 0, -5])
                        cube([2, 52, 15], center=true);
        color(oven_dark)
                translate([40.5, 0, -5])
                        cube([2, 52, 15], center=true);

        // --- Viewing window on front ---
        window_color = pcb_inside ?
                [0.95, 0.40, 0.10, 0.6] : [0.15, 0.15, 0.20, 0.5];
        color(window_color)
                translate([0, -35.5, 5])
                        cube([30, 1.5, 20], center=true);
        // Window frame
        color([0.40, 0.40, 0.43])
                translate([0, -35.5, 5])
                        difference() {
                                cube([33, 2, 23], center=true);
                                cube([29, 3, 19], center=true);
                        }

        // --- Interior glow when active ---
        if (pcb_inside) {
                glow_intensity = (progress > 0.25 && progress < 0.75) ? 0.4 : 0.2;
                glow_color = progress < 0.5 ?
                        [0.95, 0.60, 0.15, glow_intensity] :
                        [0.95, 0.30, 0.10, glow_intensity];
                color(glow_color)
                        cube([75, 60, 40], center=true);
        }

        // --- Temperature zone labels on front ---
        zone_labels = ["PREHEAT", "SOAK", "REFLOW", "COOL"];
        zone_x_pos = [-27, -9, 9, 27];
        for (i = [0:3]) {
                zone_active = (progress >= i * 0.25 && progress < (i + 1) * 0.25) ? 1 : 0;
                label_color = zone_active ?
                        [1.00, 0.90, 0.20] : [0.45, 0.45, 0.48];
                color(label_color)
                        translate([zone_x_pos[i], -36, -10])
                                rotate([90, 0, 0])
                                        linear_extrude(0.5)
                                                text(zone_labels[i], size=2.5,
                                                     halign="center",
                                                     font="Liberation Sans:style=Bold");
        }

        // --- Exhaust fan on top ---
        translate([0, 0, 27]) {
                color([0.45, 0.45, 0.48])
                        cylinder(r=10, h=8, $fn=32);
                color([0.35, 0.35, 0.38])
                        translate([0, 0, 8])
                                cylinder(r=9.5, h=0.5, $fn=32);
                // Spinning fan blades
                fan_angle = $t * 360 * 6;
                color([0.50, 0.50, 0.53])
                        translate([0, 0, 4])
                                rotate([0, 0, fan_angle])
                                        for (a = [0:90:270])
                                                rotate([0, 0, a])
                                                        translate([4, 0, 0])
                                                                cube([8, 3, 1.5], center=true);
                color([0.60, 0.60, 0.63])
                        translate([0, 0, 4])
                                cylinder(r=3, h=3, center=true, $fn=16);
        }

        // --- Temperature display ---
        color([0.08, 0.08, 0.10])
                translate([20, -36, 15])
                        cube([18, 1, 10], center=true);
        temp_color = progress < 0.50 ? [1.0, 0.85, 0.0] :
                     progress < 0.75 ? [1.0, 0.20, 0.15] : [0.20, 0.90, 0.30];
        temp_text = progress < 0.25 ? "150C" :
                    progress < 0.50 ? "200C" :
                    progress < 0.75 ? "260C" : "100C";
        color(temp_color)
                translate([20, -37, 15])
                        rotate([90, 0, 0])
                                linear_extrude(0.5)
                                        text(temp_text, size=3.5,
                                             halign="center",
                                             font="Liberation Mono:style=Bold");
}


// ========== SECTION 8: AOI INSPECTION STATION ==========

module aoi_station(scanning, scan_progress) {
        rail_color = [0.65, 0.65, 0.68];
        cam_dark = [0.20, 0.20, 0.22];

        // --- XY Linear rails ---
        color(rail_color)
                for (s = [-1, 1])
                        translate([0, s * 30, 50])
                                cube([80, 4, 4], center=true);
        // Rail support posts
        color([0.45, 0.45, 0.48])
                for (sx = [-1, 1])
                        for (sy = [-1, 1])
                                translate([sx * 38, sy * 30, 25])
                                        cube([4, 4, 50], center=true);

        // Y-axis cross rail
        cam_x = scanning ? sin(scan_progress * 360 * 3) * 30 : 0;
        cam_y = scanning ? cos(scan_progress * 360 * 1.5) * 20 : 0;
        color(rail_color)
                translate([cam_x, 0, 50])
                        cube([4, 64, 4], center=true);

        // --- Camera module ---
        translate([cam_x, cam_y, 40]) {
                color(cam_dark)
                        cube([12, 12, 15], center=true);
                // Lens pointing down
                color([0.15, 0.15, 0.30])
                        translate([0, 0, -9])
                                cylinder(r=4, h=3, $fn=24);
                color([0.10, 0.10, 0.25])
                        translate([0, 0, -10.5])
                                cylinder(r=3.5, h=0.5, $fn=24);
                // Ring light LEDs
                ring_b = scanning ? 0.95 : 0.3;
                for (a = [0:45:315])
                        color([ring_b, ring_b, ring_b])
                                translate([5.5 * cos(a), 5.5 * sin(a), -8])
                                        sphere(r=1, $fn=10);
        }

        // --- Scanning laser ---
        if (scanning) {
                color([0.10, 0.90, 0.20, 0.5])
                        translate([cam_x, cam_y, 20])
                                cylinder(r=0.5, h=20, $fn=8);
                color([0.20, 1.00, 0.30, 0.7])
                        translate([cam_x, cam_y, 0.5])
                                cylinder(r=2, h=0.5, $fn=16);
        }

        // --- Pass/fail traffic light ---
        translate([42, -20, 35]) {
                color([0.25, 0.25, 0.28])
                        cube([8, 8, 18], center=true);
                pass_on = (scanning && scan_progress > 0.9) ? 1 : 0;
                color(pass_on ? [0.10, 0.95, 0.20] : [0.15, 0.20, 0.15])
                        translate([0, -4.5, 4])
                                sphere(r=3, $fn=16);
                color([0.20, 0.12, 0.12])
                        translate([0, -4.5, -4])
                                sphere(r=3, $fn=16);
        }

        // --- PASS text ---
        if (scanning && scan_progress > 0.9)
                color([0.10, 0.95, 0.20])
                        translate([42, -32, 35])
                                rotate([90, 0, 0])
                                        linear_extrude(0.5)
                                                text("PASS", size=5,
                                                     halign="center",
                                                     font="Liberation Sans:style=Bold");

        // --- Display panel ---
        color([0.08, 0.08, 0.10])
                translate([-42, -20, 40])
                        cube([20, 2, 14], center=true);
        scan_text_c = scanning ? [0.00, 0.90, 1.00] : [0.30, 0.30, 0.35];
        color(scan_text_c)
                translate([-42, -22, 42])
                        rotate([90, 0, 0])
                                linear_extrude(0.5)
                                        text(scanning && scan_progress < 0.9 ?
                                             "SCANNING..." : "PASS - OK",
                                             size=2.5, halign="center",
                                             font="Liberation Mono:style=Bold");
}


// ========== SECTION 9: AGV TRANSPORT ROBOT ==========

function agv_pos(t) =
        t < 0.82 ? [300, -60, 90]
        : t < 0.88 ? let(f = phase(t, 0.82, 0.88))
                [lerp(300, 240, f), lerp(-60, 0, f), lerp(90, 180, f)]
        : t < 0.91 ? [240, 0, 180]
        : let(f = phase(t, 0.91, 1.00))
                [lerp(240, 320, f), lerp(0, -60, f), lerp(180, 90, f)];

module agv_robot(x, y, heading, loaded) {
        agv_body_c = [0.15, 0.55, 0.60];
        wheel_dark = [0.10, 0.10, 0.10];
        lidar_dk = [0.25, 0.25, 0.28];

        translate([x, y, 0])
        rotate([0, 0, heading]) {
                // --- Chassis ---
                color(agv_body_c)
                        hull()
                                for (cx = [-18, 18])
                                        for (cy = [-14, 14])
                                                translate([cx, cy, 5])
                                                        cylinder(r=4, h=10, $fn=16);

                // --- Wheels ---
                color(wheel_dark)
                        for (s = [-1, 1])
                                translate([0, s * 19, 8])
                                        rotate([90, 0, 0])
                                                cylinder(r=8, h=4, center=true, $fn=24);
                color([0.50, 0.50, 0.52])
                        for (s = [-1, 1])
                                translate([0, s * 19, 8])
                                        rotate([90, 0, 0])
                                                cylinder(r=3, h=5, center=true, $fn=16);

                // --- Rear caster ---
                color([0.50, 0.50, 0.52])
                        translate([-16, 0, 3])
                                sphere(r=3, $fn=16);

                // --- LiDAR dome ---
                translate([8, 0, 16]) {
                        color(lidar_dk)
                                cylinder(r=6, h=3, $fn=24);
                        translate([0, 0, 3])
                        rotate([0, 0, $t * 360 * 10]) {
                                color(lidar_dk)
                                        cylinder(r=5, h=4, $fn=24);
                                color([0.10, 0.40, 0.80])
                                        translate([4.5, 0, 2])
                                                cube([1.5, 3, 3], center=true);
                        }
                        color([0.60, 0.60, 0.63])
                                translate([0, 0, 7])
                                        sphere(r=2.5, $fn=16);
                }

                // --- Proximity sensors ---
                color([0.50, 0.15, 0.15])
                        for (cx = [-1, 1])
                                for (cy = [-1, 1])
                                        translate([cx * 20, cy * 16, 12])
                                                cylinder(r=1.5, h=3, $fn=10);
                color([0.15, 0.80, 0.25])
                        for (cx = [-1, 1])
                                for (cy = [-1, 1])
                                        translate([cx * 20, cy * 16, 15.5])
                                                sphere(r=0.8, $fn=8);

                // --- Battery indicator ---
                for (i = [0:2])
                        color(i < 2 ? [0.10, 0.80, 0.20] : [0.90, 0.80, 0.10])
                                translate([-14 + i * 5, 10, 16])
                                        cube([3, 6, 1.5], center=true);

                // --- Loaded board ---
                if (loaded) {
                        translate([0, 0, 17]) {
                                color([0.05, 0.45, 0.15])
                                        cube([68.6, 53.4, 1.6], center=true);
                                color([0.10, 0.10, 0.12])
                                        translate([8, 2, 1])
                                                cube([34, 8, 2], center=true);
                                color([0.75, 0.75, 0.78])
                                        translate([-28, 0, 1])
                                                cube([12, 12, 8], center=true);
                        }
                        color([0.45, 0.45, 0.48])
                                for (cx = [-1, 1])
                                        for (cy = [-1, 1])
                                                translate([cx * 30, cy * 22, 16])
                                                        cube([3, 2, 5], center=true);
                }

                // --- Label ---
                color([0.90, 0.90, 0.92])
                        translate([0, -16, 16])
                                linear_extrude(0.3)
                                        text("AGV", size=4, halign="center",
                                             font="Liberation Sans:style=Bold");
        }
}

module agv_path() {
        path_c = [0.60, 0.80, 0.20, 0.5];
        color(path_c) {
                for (i = [0:5])
                        translate([245 + i * 8, 0, 0.3])
                                cube([5, 1.5, 0.3], center=true);
                for (i = [0:5]) {
                        a = i * 15;
                        translate([290 + 15 * cos(270 + a), -15 * sin(270 + a), 0.3])
                                sphere(r=1, $fn=8);
                }
                for (i = [0:5])
                        translate([305, -10 - i * 8, 0.3])
                                cube([1.5, 5, 0.3], center=true);
        }
}
// =====================================================================
// Section 10: Factory Workers
// Section 11: Factory Floor & Environment
// Section 12: Production Monitor HUD
// Section 13: Main Assembly
// =====================================================================

// ========== SECTION 10: FACTORY WORKERS ==========

module factory_worker(pose, vest_color, hat_color, has_clipboard) {
        skin_c = [0.85, 0.70, 0.55];
        pants_c = [0.20, 0.22, 0.30];
        boot_c = [0.12, 0.12, 0.14];
        glasses_c = [0.10, 0.10, 0.12];
        reflective = [0.80, 0.90, 0.20];

        // Visible animation
        head_nod = sin($t * 360 * 2) * 10;
        weight_shift = sin($t * 360) * 3;
        // Arm gesture animation (clipboard raise / pointing sweep)
        arm_gesture = sin($t * 360 * 1.5) * 15;

        translate([weight_shift, 0, 0]) {
                // --- Legs & boots ---
                for (s = [-1, 1]) {
                        // Leg with walking sway
                        leg_angle = s * sin($t * 360) * 5;
                        color(pants_c)
                                translate([s * 2.5, 0, 13])
                                        rotate([leg_angle, 0, 0])
                                                translate([0, 0, -10])
                                                        cylinder(r=2, h=10, $fn=12);
                        // Boot
                        color(boot_c)
                                translate([s * 2.5, 1, 1.5])
                                        cube([4, 5, 3], center=true);
                }

                // --- Torso ---
                translate([0, 0, 13]) {
                        // Body
                        color([0.30, 0.30, 0.35])
                                cylinder(r=4, h=10, $fn=16);
                        // Safety vest overlay
                        color(vest_color)
                                translate([0, -0.5, 5])
                                        cube([9, 7, 9], center=true);
                        // Reflective strips
                        color(reflective) {
                                translate([0, -4, 3])
                                        cube([9, 0.5, 1], center=true);
                                translate([0, -4, 7])
                                        cube([9, 0.5, 1], center=true);
                        }
                }

                // --- Arms ---
                // Left arm (at side with slight swing)
                left_swing = sin($t * 360 * 1.2) * 8;
                color(skin_c) {
                        translate([-5, 0, 22])
                                rotate([10 + left_swing, 0, 5])
                                        cylinder(r=1.5, h=8, $fn=10);
                        translate([-5.5, 2, 15])
                                rotate([30 + left_swing * 0.5, 0, 0])
                                        cylinder(r=1.3, h=6, $fn=10);
                }

                // Right arm depends on pose
                if (pose == 1) {
                        // Supervisor: holding clipboard, raises it periodically to read
                        clipboard_raise = arm_gesture;
                        color(skin_c) {
                                translate([5, 0, 22])
                                        rotate([30 + clipboard_raise, 0, -5])
                                                cylinder(r=1.5, h=8, $fn=10);
                                translate([6, -5, 17])
                                        rotate([60 + clipboard_raise * 0.7, 0, 0])
                                                cylinder(r=1.3, h=6, $fn=10);
                        }
                        // Clipboard
                        if (has_clipboard) {
                                color([0.50, 0.35, 0.15])
                                        translate([6, -8 - clipboard_raise * 0.1, 17])
                                                rotate([70 + clipboard_raise * 0.5, 0, 5])
                                                        cube([6, 0.5, 8], center=true);
                                // Paper on clipboard
                                color([0.95, 0.95, 0.92])
                                        translate([6, -7.6 - clipboard_raise * 0.1, 17])
                                                rotate([70 + clipboard_raise * 0.5, 0, 5])
                                                        cube([5, 0.3, 7], center=true);
                                // Pen in hand
                                color([0.10, 0.10, 0.80])
                                        translate([8, -9, 17])
                                                rotate([75 + clipboard_raise * 0.5, 10, 0])
                                                        cylinder(r=0.4, h=5, $fn=6);
                        }
                } else if (pose == 2) {
                        // Technician: pointing at display, sweeping finger
                        point_sweep = arm_gesture;
                        color(skin_c) {
                                translate([5, 0, 22])
                                        rotate([45, 0, -10 + point_sweep * 0.5])
                                                cylinder(r=1.5, h=8, $fn=10);
                                translate([6, -6, 18])
                                        rotate([70, point_sweep * 0.3, 0])
                                                cylinder(r=1.3, h=7, $fn=10);
                        }
                        // Finger pointing
                        color(skin_c)
                                translate([7, -10, 18])
                                        rotate([75, point_sweep * 0.3, 0])
                                                cylinder(r=0.5, h=3, $fn=6);
                } else {
                        // Arms at sides
                        color(skin_c) {
                                translate([5, 0, 22])
                                        rotate([10, 0, -5])
                                                cylinder(r=1.5, h=8, $fn=10);
                                translate([5.5, 2, 15])
                                        rotate([30, 0, 0])
                                                cylinder(r=1.3, h=6, $fn=10);
                        }
                }

                // --- Head ---
                translate([0, 0, 27])
                rotate([head_nod, 0, 0]) {
                        // Head sphere
                        color(skin_c)
                                sphere(r=3.5, $fn=20);
                        // Hard hat
                        color(hat_color) {
                                translate([0, 0, 1.5])
                                        sphere(r=4, $fn=20);
                                // Brim
                                translate([0, 0, 0.5])
                                        cylinder(r=4.5, h=0.8, $fn=20);
                        }
                        // Safety glasses
                        color(glasses_c)
                                translate([0, -3.2, 0])
                                        rotate([0, 90, 0])
                                                cylinder(r=0.4, h=6, center=true, $fn=8);
                        // Eyes (behind glasses)
                        color([0.15, 0.15, 0.20])
                                for (s = [-1, 1])
                                        translate([s * 1.2, -3.3, 0.3])
                                                sphere(r=0.5, $fn=8);
                }
        }
}

module worker_supervisor() {
        scale([1.8, 1.8, 1.8])
                factory_worker(1, [0.95, 0.50, 0.10], [0.95, 0.85, 0.15], true);
}

module worker_technician() {
        scale([1.8, 1.8, 1.8])
                factory_worker(2, [0.20, 0.75, 0.30], [0.92, 0.92, 0.92], false);
}


// ========== SECTION 11: FACTORY FLOOR & ENVIRONMENT ==========

module factory_floor() {
        floor_c = [0.28, 0.28, 0.30];
        grid_c = [0.33, 0.33, 0.36];
        safety_y = [0.95, 0.85, 0.10];
        walkway_c = [0.90, 0.90, 0.92, 0.6];

        // --- Ground plane ---
        color(floor_c)
                translate([100, 0, -1])
                        cube([600, 400, 2], center=true);

        // --- Grid lines ---
        color(grid_c) {
                for (gx = [-100 : 30 : 400])
                        translate([gx, 0, 0.1])
                                cube([0.5, 400, 0.2], center=true);
                for (gy = [-180 : 30 : 180])
                        translate([100, gy, 0.1])
                                cube([600, 0.5, 0.2], center=true);
        }

        // --- Safety zone markings (yellow-black stripes around robots) ---
        // Robot 1 zone
        for (i = [0:7]) {
                stripe_c = (i % 2 == 0) ? safety_y : [0.10, 0.10, 0.12];
                color(stripe_c)
                        translate([-60 + i * 8 - 28, -65, 0.2])
                                cube([4, 2, 0.3], center=true);
                color(stripe_c)
                        translate([-60 + i * 8 - 28, 5, 0.2])
                                cube([4, 2, 0.3], center=true);
        }
        // Robot 2 zone
        for (i = [0:7]) {
                stripe_c = (i % 2 == 0) ? safety_y : [0.10, 0.10, 0.12];
                color(stripe_c)
                        translate([40 + i * 8 - 28, -65, 0.2])
                                cube([4, 2, 0.3], center=true);
                color(stripe_c)
                        translate([40 + i * 8 - 28, 5, 0.2])
                                cube([4, 2, 0.3], center=true);
        }

        // --- Safety fencing (transparent panels) ---
        fence_c = [0.70, 0.70, 0.72, 0.25];
        fence_post_c = [0.35, 0.35, 0.38];

        // Back fence (behind feeders)
        color(fence_c)
                translate([-60, 100, 30])
                        cube([200, 2, 60], center=true);
        // Fence posts
        color(fence_post_c)
                for (px = [-140, -80, -20, 40])
                        translate([px, 100, 30])
                                cylinder(r=2, h=60, center=true, $fn=12);

        // Side fences
        color(fence_c)
                translate([-160, 20, 30])
                        cube([2, 160, 60], center=true);
        color(fence_post_c)
                for (py = [-40, 20, 80])
                        translate([-160, py, 30])
                                cylinder(r=2, h=60, center=true, $fn=12);

        // --- Station labels on floor ---
        color([0.90, 0.90, 0.92]) {
                translate([-10, -85, 0.3])
                        text("SMD PLACEMENT", size=6, halign="center",
                             font="Liberation Sans:style=Bold");
                translate([160, -85, 0.3])
                        text("REFLOW", size=6, halign="center",
                             font="Liberation Sans:style=Bold");
                translate([240, -85, 0.3])
                        text("INSPECTION", size=6, halign="center",
                             font="Liberation Sans:style=Bold");
                translate([320, -85, 0.3])
                        text("OUTPUT", size=6, halign="center",
                             font="Liberation Sans:style=Bold");
        }

        // --- Flow direction arrows ---
        color([0.10, 0.70, 0.20, 0.5])
                for (ax = [-100, -30, 80, 180, 270]) {
                        translate([ax, 0, 0.3]) {
                                cube([10, 2, 0.4], center=true);
                                translate([6, 0, 0])
                                        rotate([0, 0, -90])
                                                cylinder(h=0.4, r=3, $fn=3, center=true);
                        }
                }

        // --- Emergency stop buttons (near each robot) ---
        for (estop_x = [-60, 40]) {
                translate([estop_x, -70, 0]) {
                        // Pedestal
                        color([0.25, 0.25, 0.28])
                                cube([8, 8, 25], center=true);
                        // Yellow ring
                        color([0.95, 0.85, 0.10])
                                translate([0, 0, 13])
                                        cylinder(r=6, h=2, $fn=24);
                        // Red mushroom button
                        color([0.90, 0.10, 0.10])
                                translate([0, 0, 15])
                                        cylinder(r=5, h=4, $fn=24);
                        color([0.80, 0.08, 0.08])
                                translate([0, 0, 19])
                                        sphere(r=5, $fn=20);
                        // Label
                        color([0.95, 0.95, 0.95])
                                translate([0, -5, 8])
                                        rotate([90, 0, 0])
                                                linear_extrude(0.3)
                                                        text("E-STOP", size=2.5,
                                                             halign="center",
                                                             font="Liberation Sans:style=Bold");
                }
        }

        // --- Worker walkway paths (white dashed lines) ---
        color(walkway_c)
                for (i = [0:15])
                        translate([-150 + i * 30, -100, 0.2])
                                cube([15, 2, 0.3], center=true);
        color(walkway_c)
                for (i = [0:15])
                        translate([-150 + i * 30, 130, 0.2])
                                cube([15, 2, 0.3], center=true);
}


// ========== SECTION 12: PRODUCTION MONITOR HUD ==========

module production_hud(t_anim, n_comp) {
        hud_bg_c   = [0.10, 0.10, 0.15];
        hud_txt    = [0.00, 0.90, 1.00];
        hud_grn    = [0.20, 1.00, 0.30];
        hud_wrn    = [1.00, 0.85, 0.00];
        hud_frame  = [0.30, 0.30, 0.35];

        // --- Panel body (wall-mounted) ---
        color(hud_bg_c)
                cube([120, 3, 80], center=true);
        // Frame border
        color(hud_frame)
                difference() {
                        cube([124, 4, 84], center=true);
                        cube([120, 5, 80], center=true);
                }

        // --- Title ---
        color(hud_txt)
                translate([0, -2, 32])
                        rotate([90, 0, 0])
                                linear_extrude(0.5)
                                        text("ARDUINO UNO ASSEMBLY LINE",
                                             size=4, halign="center",
                                             font="Liberation Sans:style=Bold");

        // --- Current phase display ---
        // Show phase name based on t_anim
        phase_text =
                t_anim < 0.08 ? "PCB LOADING" :
                t_anim < 0.18 ? "PLACING ATMEGA328P" :
                t_anim < 0.28 ? "PLACING CRYSTAL" :
                t_anim < 0.38 ? "PLACING USB-B" :
                t_anim < 0.48 ? "PLACING CAPACITORS" :
                t_anim < 0.55 ? "PLACING VREG" :
                t_anim < 0.62 ? "PLACING HEADERS" :
                t_anim < 0.72 ? "REFLOW SOLDERING" :
                t_anim < 0.82 ? "AOI INSPECTION" :
                "AGV TRANSPORT";

        color(hud_wrn)
                translate([0, -2, 24])
                        rotate([90, 0, 0])
                                linear_extrude(0.5)
                                        text(phase_text, size=3.5,
                                             halign="center",
                                             font="Liberation Mono:style=Bold");

        // --- Components counter ---
        color(hud_grn)
                translate([-50, -2, 16])
                        rotate([90, 0, 0])
                                linear_extrude(0.5)
                                        text(str("Components: ", n_comp, "/7"),
                                             size=3.5, halign="left",
                                             font="Liberation Mono:style=Bold");

        // --- Cycle time & rate ---
        color(hud_txt)
                translate([-50, -2, 9])
                        rotate([90, 0, 0])
                                linear_extrude(0.5)
                                        text("Cycle: 42.0s | Rate: 85 bds/hr",
                                             size=3, halign="left",
                                             font="Liberation Mono");

        // --- OEE display with bar ---
        color(hud_txt)
                translate([-50, -2, 2])
                        rotate([90, 0, 0])
                                linear_extrude(0.5)
                                        text("OEE: 87.3%", size=3,
                                             halign="left", font="Liberation Mono");
        // OEE bar background
        color([0.20, 0.20, 0.25])
                translate([15, -2, -2])
                        cube([60, 1, 4], center=true);
        // OEE bar fill
        color(hud_grn)
                translate([15 - 30 + 0.873 * 30, -2.5, -2])
                        cube([0.873 * 60, 1.5, 4], center=true);

        // --- Progress bar ---
        bar_w = 100;
        // Background
        color([0.20, 0.20, 0.25])
                translate([0, -2, -10])
                        cube([bar_w + 4, 1, 6], center=true);
        // Fill
        color([0.00, 0.80, 0.90])
                translate([-bar_w/2 + t_anim * bar_w / 2, -2.5, -10])
                        cube([t_anim * bar_w, 1.5, 5], center=true);
        // Phase markers
        phase_ts = [0.08, 0.18, 0.28, 0.38, 0.48, 0.55, 0.62, 0.72, 0.82];
        color([0.90, 0.90, 0.92])
                for (i = [0:8])
                        translate([-bar_w/2 + phase_ts[i] * bar_w, -2, -10])
                                cube([0.5, 2, 6], center=true);

        // --- Board counter ---
        color(hud_grn)
                translate([-50, -2, -18])
                        rotate([90, 0, 0])
                                linear_extrude(0.5)
                                        text("Boards Today: 847",
                                             size=3, halign="left",
                                             font="Liberation Mono:style=Bold");

        // --- Quality yield ---
        color(hud_grn)
                translate([-50, -2, -24])
                        rotate([90, 0, 0])
                                linear_extrude(0.5)
                                        text("First Pass Yield: 98.2%",
                                             size=3, halign="left",
                                             font="Liberation Mono:style=Bold");

        // --- Percentage label ---
        color([0.85, 0.85, 0.85])
                translate([bar_w/2 + 5, -2, -10])
                        rotate([90, 0, 0])
                                linear_extrude(0.5)
                                        text(str(floor(t_anim * 100), "%"),
                                             size=3.5, halign="left",
                                             font="Liberation Sans:style=Bold");
}


// ========== SECTION 13: MAIN ASSEMBLY ==========

module main_assembly() {
        // --- Compute animation state ---
        n_comp = components_placed($t);
        board_x = pcb_x($t);

        // PCB in oven?
        pcb_in_oven = ($t >= 0.62 && $t < 0.72) ? 1 : 0;
        oven_progress = pcb_in_oven ? phase($t, 0.62, 0.72) : 0;

        // AOI scanning?
        aoi_scanning = ($t >= 0.72 && $t < 0.82) ? 1 : 0;
        aoi_progress = aoi_scanning ? phase($t, 0.72, 0.82) : 0;

        // AGV state
        agv = agv_pos($t);
        agv_loaded = ($t >= 0.88) ? 1 : 0;

        // PCB visible on conveyor (not on AGV and not in oven center)
        pcb_on_conveyor = ($t < 0.88) ? 1 : 0;

        // SCARA state
        s1 = scara1_state($t);
        // Articulated arm state
        a2 = arm2_state($t);

        // === Place factory floor ===
        factory_floor();

        // === Conveyor belt ===
        conveyor_belt(400, 50, $t);

        // === PCB on carrier on conveyor ===
        if (pcb_on_conveyor) {
                translate([board_x, 0, leg_height + belt_height + 1]) {
                        pcb_carrier(0);
                        translate([0, 0, 3])
                                arduino_pcb(n_comp);
                }
        }

        // === Component feeder station ===
        translate([feeder_x - 40, 50, leg_height + belt_height + 2])
                component_feeder_station(n_comp);

        // === SCARA Robot (Robot 1) ===
        translate([scara_x, -50, 0])
                scara_robot(s1[0], s1[1], s1[2], s1[3], s1[4]);

        // === Articulated Robot (Robot 2) ===
        translate([artic_x, -50, 0])
                articulated_robot(a2[0], a2[1], a2[2], a2[3], a2[4], a2[5], a2[6]);

        // === Reflow Oven ===
        translate([160, 0, leg_height + belt_height + 25])
                reflow_oven(pcb_in_oven, oven_progress);

        // === AOI Inspection Station ===
        translate([aoi_x, 0, leg_height + belt_height])
                aoi_station(aoi_scanning, aoi_progress);

        // === AGV ===
        agv_robot(agv[0], agv[1], agv[2], agv_loaded);
        agv_path();

        // === Factory workers ===
        // Supervisor near robot 1 area, facing conveyor
        translate([-20, -65, 0])
                rotate([0, 0, 20])
                        worker_supervisor();

        // QC Technician near AOI station, facing inspection display
        translate([aoi_x + 10, -60, 0])
                rotate([0, 0, -15])
                        worker_technician();

        // === Production Monitor HUD (back wall) ===
        translate([100, 140, leg_height + 50])
                rotate([0, 0, 0])
                        production_hud($t, n_comp);

        // === Title ===
        color([0.90, 0.90, 0.92])
                translate([100, -160, 0.5])
                        text("Factory Robot Simulation — Arduino Uno SMT Assembly Line",
                             size=7, halign="center",
                             font="Liberation Sans:style=Bold");

        // === Subtitle ===
        color([0.65, 0.65, 0.68])
                translate([100, -172, 0.5])
                        text("SCARA + 6-DOF Articulated + AGV  |  10-Phase Assembly Cycle  |  Reflow & AOI",
                             size=4, halign="center", font="Liberation Sans");
}

// === RENDER THE SCENE ===
main_assembly();
