// Slider-Crank Mechanism — Animated with $t
// Uses $t (0..1) for one full crank revolution
//
// Parameters
crank_r     = 30;       // crank radius (mm)
rod_len     = 80;       // connecting rod length (mm)
thickness   = 6;        // link thickness (mm)
link_w      = 10;       // link width (mm)
pin_r       = 3;        // pin/joint radius (mm)
slider_w    = 24;       // slider block width (mm)
slider_h    = 16;       // slider block height (mm)
rail_len    = 140;      // slider rail length (mm)
base_w      = 180;      // base plate width (mm)
base_d      = 60;       // base plate depth (mm)
base_t      = 3;        // base plate thickness (mm)

// Kinematics
theta = $t * 360;                                       // crank angle (deg)
crank_x = crank_r * cos(theta);
crank_y = crank_r * sin(theta);
// Slider x-position from geometry
slider_x = crank_x + sqrt(rod_len*rod_len - crank_y*crank_y);
// Connecting rod angle
rod_angle = atan2(-crank_y, slider_x - crank_x);

// Colors
crank_color  = [0.85, 0.25, 0.25];   // red
rod_color    = [0.25, 0.55, 0.85];   // blue
slider_color = [0.30, 0.75, 0.35];   // green
pin_color    = [0.90, 0.90, 0.90];   // silver
base_color   = [0.40, 0.40, 0.45];   // dark gray
rail_color   = [0.60, 0.60, 0.60];   // gray

module rounded_link(length, width, thick) {
    // A link with rounded ends
    hull() {
        cylinder(h=thick, r=width/2, center=true, $fn=32);
        translate([length, 0, 0])
            cylinder(h=thick, r=width/2, center=true, $fn=32);
    }
}

module pin(height) {
    color(pin_color)
        cylinder(h=height, r=pin_r, center=true, $fn=24);
}

module joint_bore(thick) {
    cylinder(h=thick+1, r=pin_r+0.5, center=true, $fn=24);
}

// ---- Base plate ----
color(base_color)
    translate([rail_len/2 - 20, 0, -base_t/2 - thickness/2 - 2])
        cube([base_w, base_d, base_t], center=true);

// ---- Ground pivot (fixed bearing) ----
color(pin_color)
    translate([0, 0, 0])
        cylinder(h=thickness+4, r=pin_r+2, center=true, $fn=32);

// ---- Crank ----
rotate([0, 0, theta])
    translate([0, 0, thickness/2 + 1]) {
        color(crank_color)
            difference() {
                rounded_link(crank_r, link_w, thickness);
                // Bore at pivot
                joint_bore(thickness);
                // Bore at crank pin
                translate([crank_r, 0, 0])
                    joint_bore(thickness);
            }
        // Crank pin
        translate([crank_r, 0, 0])
            pin(thickness + 2);
    }

// ---- Connecting rod ----
translate([crank_x, crank_y, -(thickness/2 + 1)])
    rotate([0, 0, rod_angle]) {
        color(rod_color)
            difference() {
                rounded_link(rod_len, link_w, thickness);
                joint_bore(thickness);
                translate([rod_len, 0, 0])
                    joint_bore(thickness);
            }
    }

// ---- Slider rail ----
color(rail_color)
    translate([rail_len/2 - 20, 0, -(thickness/2 + 1)]) {
        // Top rail
        translate([0, 0, slider_h/2 + thickness/2 + 1])
            cube([rail_len, link_w/2, 2], center=true);
        // Bottom rail
        translate([0, 0, -(slider_h/2 + thickness/2 + 1)])
            cube([rail_len, link_w/2, 2], center=true);
    }

// ---- Slider block ----
translate([slider_x, 0, -(thickness/2 + 1)]) {
    color(slider_color)
        difference() {
            cube([slider_w, slider_w, slider_h], center=true);
            // Wrist pin bore
            cylinder(h=slider_h+1, r=pin_r+0.5, center=true, $fn=24);
        }
    // Wrist pin
    pin(slider_h + 2);
}

// ---- Ground pivot pin (on top) ----
translate([0, 0, 0])
    pin(thickness * 3);
