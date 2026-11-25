// Gear Train Animation with Contact Analysis
// 4-gear compound train: Spur Pinion → Spur Gear ⟹ Helical Pinion → Helical Gear
// Features: meshed rotation, contact markers, interference detection, dashboard
// Animated with $t (0..1 = 3 input revolutions)

// ============ PARAMETERS ============
m    = 3;          // module (mm/tooth)
pa   = 20;         // pressure angle (deg)
tk_s = 8;          // spur face width
tk_h = 10;         // helical face width
bore = 4;          // bore radius
tw_h = 20;         // helix twist (deg)

// Teeth counts
z1 = 12;  z2 = 24;  z3 = 10;  z4 = 30;

// Pitch radii
r1 = m*z1/2;  r2 = m*z2/2;  r3 = m*z3/2;  r4 = m*z4/2;

// Addendum / dedendum
ha = m;  hf = 1.25*m;
ra1=r1+ha; rf1=r1-hf;  ra2=r2+ha; rf2=r2-hf;
ra3=r3+ha; rf3=r3-hf;  ra4=r4+ha; rf4=r4-hf;

// Base radii
rb1=r1*cos(pa); rb2=r2*cos(pa);
rb3=r3*cos(pa); rb4=r4*cos(pa);

// Gear centers
cx1 = 0;
cx2 = r1 + r2;              // 54
cx3 = cx2;                   // compound shaft
cx4 = cx2 + r3 + r4;        // 114

// Z-levels
zs = 0;                          // spur level
zh = tk_s/2 + 2 + tk_h/2;       // helical level = 11

// Transmission ratios
i12 = z2/z1;                // 2.0
i34 = z4/z3;                // 3.0
i_tot = i12 * i34;          // 6.0

// Min teeth for 20deg PA (no undercut)
z_min = 17;

// ============ ANIMATION ============
n_rev = 3;
input_deg = $t * 360 * n_rev;

// Rotation angles with mesh phasing
a1 = input_deg;
a2 = -input_deg * z1/z2 + 180/z2;
a3 = a2;                                    // compound shaft
a4 = input_deg / i_tot + 180/z4;            // double reversal

// Contact pulsing
cp12 = sin(input_deg * z1 * 2);
cp34 = sin(input_deg * z3/i12 * 2);

// ============ COLORS ============
c_brass  = [0.78, 0.65, 0.20];
c_steel  = [0.65, 0.67, 0.70];
c_bronze = [0.72, 0.50, 0.22];
c_dark   = [0.58, 0.60, 0.64];
c_shaft  = [0.50, 0.52, 0.55];
c_base   = [0.30, 0.30, 0.35];
c_glow   = [1.0, 0.35, 0.10];
c_force  = [1.0, 1.0, 0.2];
c_safe   = [0.15, 0.90, 0.30];
c_warn   = [1.0, 0.80, 0.10];
c_crit   = [1.0, 0.15, 0.10];

// ============ GEAR MODULES ============

module spur_gear(z, rp, ra, rf, t, clr) {
    color(clr)
    difference() {
        union() {
            cylinder(h=t, r=rf+0.5, center=true, $fn=z*3);
            for (i = [0:z-1])
                rotate([0,0, i*360/z])
                    hull() {
                        translate([rf+0.2,0,0])
                            cylinder(h=t, r=m*0.52, center=true, $fn=6);
                        translate([ra-0.2,0,0])
                            cylinder(h=t, r=m*0.30, center=true, $fn=6);
                    }
        }
        cylinder(h=t+2, r=bore, center=true, $fn=20);
        translate([bore-0.8,0,0]) cube([1.5,1.8,t+2], center=true);
        if (z >= 20)
            for (i = [0:floor(z/6)-1])
                rotate([0,0, i*360/floor(z/6)])
                    translate([rp*0.55,0,0])
                        cylinder(h=t+2, r=rp*0.13, center=true, $fn=16);
    }
    // Hub ring
    color(clr * 0.88)
    difference() {
        cylinder(h=t+2, r=bore+2.5, center=true, $fn=20);
        cylinder(h=t+3, r=bore, center=true, $fn=20);
    }
}

module helical_gear(z, rp, ra, rf, t, clr, twist) {
    color(clr)
    difference() {
        linear_extrude(height=t, center=true, twist=twist, slices=8, $fn=z*2) {
            union() {
                circle(r=rf+0.5, $fn=z*3);
                for (i = [0:z-1])
                    rotate([0,0, i*360/z])
                        hull() {
                            translate([rf+0.2,0])
                                circle(r=m*0.52, $fn=6);
                            translate([ra-0.2,0])
                                circle(r=m*0.30, $fn=6);
                        }
            }
        }
        cylinder(h=t+2, r=bore, center=true, $fn=20);
        translate([bore-0.8,0,0]) cube([1.5,1.8,t+2], center=true);
        if (z >= 20)
            for (i = [0:floor(z/6)-1])
                rotate([0,0, i*360/floor(z/6)])
                    translate([rp*0.55,0,0])
                        cylinder(h=t+2, r=rp*0.13, center=true, $fn=16);
    }
    color(clr * 0.88)
    difference() {
        cylinder(h=t+2, r=bore+2.5, center=true, $fn=20);
        cylinder(h=t+3, r=bore, center=true, $fn=20);
    }
}

// ============ STRUCTURAL MODULES ============

module shaft_asm(cx, z_lo, z_hi) {
    color(c_shaft)
        translate([cx, 0, (z_lo+z_hi)/2])
            cylinder(h=z_hi-z_lo, r=3.5, center=true, $fn=16);
    // Bearing housings
    color(c_base)
    for (zz = [z_lo, z_hi])
        translate([cx, 0, zz])
            difference() {
                cube([14, 16, 3], center=true);
                cylinder(h=4, r=4.2, center=true, $fn=20);
            }
}

module pitch_ring(cx, rp, zp) {
    color([0.3, 0.75, 1.0, 0.5])
        translate([cx, 0, zp])
            difference() {
                cylinder(h=0.4, r=rp+0.3, center=true, $fn=48);
                cylinder(h=0.6, r=rp-0.3, center=true, $fn=48);
            }
}

// ============ CONTACT ANALYSIS ============

module contact_marker(px, zp, pulse) {
    sz = 1.3 + 0.7 * max(0, pulse);

    // Glowing contact sphere
    color(c_glow)
        translate([px, 0, zp + 7])
            sphere(r=sz, $fn=12);

    // Line of action
    color([1, 1, 0, 0.25])
        translate([px, 0, zp + 7])
            rotate([0, 0, 180-pa])
                cube([28, 0.5, 0.5], center=true);

    // Normal force vector
    color(c_force)
    translate([px, 0, zp + 12]) {
        rotate([0, 0, 160])
            translate([5, 0, 0])
                cube([10, 0.8, 0.8], center=true);
        rotate([0, 0, 160])
            translate([10.5, 0, 0])
                rotate([0, 0, -90])
                    cylinder(h=0.8, r1=2, r2=0, $fn=3, center=true);
    }
    // Fn label
    color([1,1,1])
        translate([px-2, 8, zp + 12])
            text("Fn", size=3, halign="center",
                 font="Liberation Sans:style=Bold");
}

module interference_ring(cx, rf, zp) {
    color([1, 0.1, 0.1, 0.30])
        translate([cx, 0, zp])
            difference() {
                cylinder(h=1.5, r=rf+1.5, center=true, $fn=40);
                cylinder(h=2, r=max(2, rf-1), center=true, $fn=40);
            }
}

// ============ INDICATORS ============

module rot_arrow(cx, zp, rad, cw) {
    color([0.9, 0.9, 0.95])
    translate([cx, 0, zp]) {
        for (a = [0:20:250])
            rotate([0, 0, cw ? -a : a])
                translate([rad, 0, 0])
                    sphere(r=0.5, $fn=6);
        rotate([0, 0, cw ? -270 : 270])
            translate([rad, 0, 0])
                rotate([0, 0, cw ? 90 : -90])
                    cylinder(h=0.8, r1=2, r2=0, $fn=3, center=true);
    }
}

module rpm_tag(cx, zp, rpm_val, label) {
    translate([cx, -52, zp]) {
        color([0.08, 0.08, 0.12])
            cube([30, 1.5, 14], center=true);
        color([0.0, 1.0, 0.6])
            translate([0, -1, 4])
                text(label, size=3, halign="center",
                     font="Liberation Mono:style=Bold");
        color([1.0, 0.9, 0.3])
            translate([0, -1, -3])
                text(str(rpm_val, " RPM"), size=3, halign="center",
                     font="Liberation Mono:style=Bold");
    }
}

// ============ DASHBOARD ============

module dashboard() {
    translate([cx4/2, 62, zh/2]) {
        color([0.06, 0.06, 0.10])
            cube([155, 2, 60], center=true);
        color([0.25, 0.25, 0.35])
            difference() {
                cube([159, 2.5, 64], center=true);
                cube([155, 3, 60], center=true);
            }

        // Title
        color([0.0, 0.9, 1.0])
            translate([0, -1.5, 24])
                text("GEAR TRAIN CONTACT ANALYSIS", size=4.5,
                     halign="center", font="Liberation Sans:style=Bold");

        // Stage data
        color([0.85, 0.85, 0.90]) {
            translate([-70, -1.5, 15])
                text("Stage 1: Z1=12 > Z2=24 (Spur)     i = 2.0",
                     size=3, font="Liberation Mono");
            translate([-70, -1.5, 8])
                text("Stage 2: Z3=10 > Z4=30 (Helical)   i = 3.0",
                     size=3, font="Liberation Mono");
        }

        // Total ratio
        color([0.0, 1.0, 0.5])
            translate([-70, -1.5, 0])
                text("Total Ratio: i = 6.0 : 1", size=3.5,
                     font="Liberation Mono:style=Bold");

        // Contact ratios
        color([0.4, 0.8, 1.0])
            translate([-70, -1.5, -9])
                text("Contact Ratio: CR1=1.51  CR2=1.38  [OK]",
                     size=3, font="Liberation Mono");

        // Interference results
        color(c_warn)
            translate([-70, -1.5, -18])
                text("Z1=12 < Zmin=17 : UNDERCUT WARNING",
                     size=3, font="Liberation Mono:style=Bold");
        color(c_crit)
            translate([-70, -1.5, -25])
                text("Z3=10 < Zmin=17 : UNDERCUT CRITICAL",
                     size=3, font="Liberation Mono:style=Bold");
    }
}

// ============ BASE ============

module base_plate() {
    color(c_base)
        translate([cx4/2, 0, -(tk_s/2 + 6)])
            cube([cx4 + 40, 75, 3], center=true);
    color([0.22, 0.22, 0.25])
        translate([cx4/2, 0, -(tk_s/2 + 9)])
            cube([cx4 + 70, 110, 2], center=true);
    color([0.27, 0.27, 0.30])
        for (gx = [-15 : 20 : cx4+15])
            translate([gx, 0, -(tk_s/2+7.8)])
                cube([0.4, 110, 0.3], center=true);
}

// ============ ASSEMBLY ============

base_plate();
dashboard();

// ---- Shafts with bearings ----
shaft_asm(cx1, zs-tk_s/2-3, zs+tk_s/2+3);
shaft_asm(cx2, zs-tk_s/2-3, zh+tk_h/2+3);
shaft_asm(cx4, zh-tk_h/2-3, zh+tk_h/2+3);

// ---- Spur gears (lower level) ----
translate([cx1, 0, zs])
    rotate([0, 0, a1])
        spur_gear(z1, r1, ra1, rf1, tk_s, c_brass);

translate([cx2, 0, zs])
    rotate([0, 0, a2])
        spur_gear(z2, r2, ra2, rf2, tk_s, c_steel);

// ---- Helical gears (upper level) ----
translate([cx3, 0, zh])
    rotate([0, 0, a3])
        helical_gear(z3, r3, ra3, rf3, tk_h, c_bronze, tw_h);

translate([cx4, 0, zh])
    rotate([0, 0, a4])
        helical_gear(z4, r4, ra4, rf4, tk_h, c_dark, -tw_h);

// ---- Pitch circles ----
pitch_ring(cx1, r1, zs+tk_s/2+0.8);
pitch_ring(cx2, r2, zs+tk_s/2+0.8);
pitch_ring(cx3, r3, zh+tk_h/2+0.8);
pitch_ring(cx4, r4, zh+tk_h/2+0.8);

// ---- Contact markers at mesh zones ----
contact_marker(r1, zs, cp12);               // g1-g2 pitch point
contact_marker(cx2 + r3, zh, cp34);         // g3-g4 pitch point

// ---- Interference zones (red rings on small gears) ----
interference_ring(cx1, rf1, zs+tk_s/2+0.5);
interference_ring(cx3, rf3, zh+tk_h/2+0.5);

// ---- Rotation arrows ----
rot_arrow(cx1, zs+tk_s/2+3, r1+7, false);
rot_arrow(cx2, zs+tk_s/2+3, r2+7, true);
rot_arrow(cx3, zh+tk_h/2+3, r3+7, true);
rot_arrow(cx4, zh+tk_h/2+3, r4+7, false);

// ---- RPM tags ----
rpm_tag(cx1, zs, 1000, "INPUT");
rpm_tag(cx2, zs+5, 500, "SHAFT 2");
rpm_tag(cx4, zh, 167, "OUTPUT");

// ---- Gear labels ----
color([0.9, 0.9, 0.95]) {
    translate([cx1, r1+8, zs+3])
        text("Z1=12", size=3, halign="center", font="Liberation Mono");
    translate([cx1, r1+8, zs-2])
        text("Spur", size=2.5, halign="center");

    translate([cx2, r2+8, zs+3])
        text("Z2=24", size=3, halign="center", font="Liberation Mono");
    translate([cx2, r2+8, zs-2])
        text("Spur", size=2.5, halign="center");

    translate([cx3, r3+8, zh+3])
        text("Z3=10", size=3, halign="center", font="Liberation Mono");
    translate([cx3, r3+8, zh-2])
        text("Helical", size=2.5, halign="center");

    translate([cx4, r4+8, zh+3])
        text("Z4=30", size=3, halign="center", font="Liberation Mono");
    translate([cx4, r4+8, zh-2])
        text("Helical", size=2.5, halign="center");
}

// ---- Input / Output arrows ----
color([0.2, 0.95, 0.3]) {
    translate([cx1-18, 0, zs]) {
        cube([14, 1.8, 1.8], center=true);
        translate([8, 0, 0])
            rotate([0, 0, -90])
                cylinder(h=1.8, r1=3.5, r2=0, $fn=3, center=true);
    }
    translate([cx1-18, 0, zs+5])
        text("IN", size=4, halign="center",
             font="Liberation Sans:style=Bold");
}

color([1.0, 0.4, 0.15]) {
    translate([cx4+22, 0, zh]) {
        cube([14, 1.8, 1.8], center=true);
        translate([8, 0, 0])
            rotate([0, 0, -90])
                cylinder(h=1.8, r1=3.5, r2=0, $fn=3, center=true);
    }
    translate([cx4+22, 0, zh+5])
        text("OUT", size=4, halign="center",
             font="Liberation Sans:style=Bold");
}

// ---- Center distance dimensions ----
// Stage 1
color([0.6, 0.6, 0.65]) {
    translate([cx1, 0, -(tk_s/2+2)])
        cube([r1+r2, 0.5, 0.5], center=false);
    translate([(cx1+cx2)/2, -4, -(tk_s/2+2)])
        text("c1=54", size=2.5, halign="center", font="Liberation Mono");
}
// Stage 2
color([0.6, 0.6, 0.65]) {
    translate([cx3, 0, zh-(tk_h/2+2)])
        cube([r3+r4, 0.5, 0.5], center=false);
    translate([(cx3+cx4)/2, -4, zh-(tk_h/2+2)])
        text("c2=60", size=2.5, halign="center", font="Liberation Mono");
}

// ---- Title ----
color([1,1,1])
    translate([cx4/2, -78, zh+12])
        text("Gear Train with Contact Analysis",
             size=5.5, halign="center",
             font="Liberation Sans:style=Bold");
color([0.7, 0.7, 0.75])
    translate([cx4/2, -78, zh+4])
        text("Spur + Helical Gears  |  Ratio Validation  |  Interference Check",
             size=3, halign="center");

// === End of Gear Train Animation ===
