// Peaucellier-Lipkin Linkage (Eight-Bar) — Exact Straight-Line Mechanism
// Uses $t (0..1) for one full operating cycle
// Point P traces a perfect vertical straight line via circle inversion
//
// The 8 bars:
//   1. Ground:     O  <-> O'  (fixed, length d)
//   2. Crank:      O' ->  A   (driven, length d)
//   3. Long link:  O  ->  B   (length L)
//   4. Long link:  O  ->  C   (length L)
//   5. Rhombus:    A  ->  B   (length s)
//   6. Rhombus:    B  ->  P   (length s)
//   7. Rhombus:    P  ->  C   (length s)
//   8. Rhombus:    C  ->  A   (length s)

// ---- Parameters (mm) ----
d       = 45;          // fixed pivot distance O<->O', also crank length
L       = 65;          // long links OB, OC
s       = 30;          // rhombus side lengths AB, BC, CP, PA
thickness = 6;         // link thickness
link_w  = 10;          // link width
pin_r   = 3;           // pin/joint radius
base_w  = 240;         // base plate width
base_d  = 200;         // base plate depth
base_t  = 4;           // base plate thickness

// Inversion constant
inv_k   = L*L - s*s;   // = 3325

// ---- Kinematics ----
// Operating range: theta in [50, 310] degrees (avoids singularity at theta=0)
theta = 50 + $t * 260;

// Fixed pivots
O_x  = 0;
O_y  = 0;
Op_x = -d;             // O' = (-45, 0)
Op_y = 0;

// Point A (crank tip, driven)
A_x = -d + d * cos(theta);
A_y = d * sin(theta);

// Point P (output, traces straight line via inversion)
OA_sq = A_x*A_x + A_y*A_y;
k     = inv_k / OA_sq;
P_x   = k * A_x;       // constant ~ -36.944 for all theta
P_y   = k * A_y;

// Midpoint of AP diagonal (center of rhombus)
M_x = (A_x + P_x) / 2;
M_y = (A_y + P_y) / 2;

// Points B and C (rhombus corners, symmetric about line AP)
AC_x   = P_x - A_x;
AC_y   = P_y - A_y;
AC_len = sqrt(AC_x*AC_x + AC_y*AC_y);
half_BP = sqrt(s*s - (AC_len/2)*(AC_len/2));

perp_x = -AC_y / AC_len;   // unit perpendicular to AP
perp_y =  AC_x / AC_len;

B_x = M_x + half_BP * perp_x;
B_y = M_y + half_BP * perp_y;
C_x = M_x - half_BP * perp_x;
C_y = M_y - half_BP * perp_y;

// ---- Z Layers ----
z_base    = -base_t/2 - 2;
z_ground  = 1;                              // ground bar
z_long    = z_ground + thickness + 2;       // long links OB, OC
z_crank   = z_long + thickness + 2;         // crank O'A
z_rhombus = z_crank + thickness + 2;        // rhombus links

// ---- Colors ----
crank_color   = [0.85, 0.25, 0.25];   // red — crank O'A
long_color    = [0.25, 0.55, 0.85];   // blue — long links OB, OC
rhombus_color = [0.20, 0.70, 0.55];   // teal — rhombus links
output_color  = [0.95, 0.75, 0.10];   // gold — point P
ground_color  = [0.45, 0.45, 0.50];   // dark gray — ground bar O-O'
pin_color     = [0.90, 0.90, 0.90];   // silver — pins
base_color    = [0.35, 0.35, 0.40];   // dark gray — base plate
trail_color   = [0.90, 0.75, 0.10];   // warm gold — straight-line trail
label_color   = [0.75, 0.75, 0.80];   // light gray — labels

// ---- Modules ----
module rounded_link(length, width, thick) {
        // A link with rounded ends, oriented along +X
        hull() {
                cylinder(h=thick, r=width/2, center=true, $fn=32);
                translate([length, 0, 0])
                        cylinder(h=thick, r=width/2, center=true, $fn=32);
        }
}

module pin_shaft(height) {
        color(pin_color)
                cylinder(h=height, r=pin_r, center=true, $fn=24);
}

module joint_bore(thick) {
        cylinder(h=thick+2, r=pin_r+0.5, center=true, $fn=24);
}

module link_between(x1, y1, x2, y2, z_layer, col) {
        // Draw a link from (x1,y1) to (x2,y2) at given Z layer
        dx = x2 - x1;
        dy = y2 - y1;
        len = sqrt(dx*dx + dy*dy);
        ang = atan2(dy, dx);
        translate([x1, y1, z_layer])
                rotate([0, 0, ang]) {
                        color(col)
                                difference() {
                                        rounded_link(len, link_w, thickness);
                                        joint_bore(thickness);
                                        translate([len, 0, 0])
                                                joint_bore(thickness);
                                }
                }
}

module bearing(x, y) {
        // Fixed pivot bearing cylinder
        color(pin_color)
                translate([x, y, z_ground])
                        cylinder(h=thickness+4, r=pin_r+2.5, center=true, $fn=32);
}

module joint_pin(x, y, z_low, z_high) {
        // Pin shaft spanning from z_low to z_high
        h = z_high - z_low + thickness + 4;
        color(pin_color)
                translate([x, y, (z_low + z_high) / 2])
                        cylinder(h=h, r=pin_r, center=true, $fn=24);
}

module point_label(x, y, z_layer, txt, offset_x, offset_y) {
        color(label_color)
                translate([x + offset_x, y + offset_y, z_layer + thickness/2 + 1])
                        text(txt, size=5, halign="center", valign="center",
                             font="Liberation Sans:style=Bold");
}

// ================================================================
// SCENE
// ================================================================

// ---- Base plate ----
color(base_color)
        translate([-30, 0, z_base])
                cube([base_w, base_d, base_t], center=true);

// ---- Title ----
color([0.85, 0.85, 0.85])
        translate([-30, base_d/2 - 18, z_base + base_t/2 + 0.5])
                text("Peaucellier-Lipkin Linkage (Eight-Bar)", size=7,
                     halign="center", font="Liberation Sans:style=Bold");

// ---- Subtitle ----
color([0.65, 0.65, 0.65])
        translate([-30, -base_d/2 + 10, z_base + base_t/2 + 0.5])
                text("Exact Straight-Line Mechanism", size=5,
                     halign="center", font="Liberation Sans");

// ---- Fixed pivot bearings ----
bearing(O_x, O_y);
bearing(Op_x, Op_y);

// ---- Vertical guide line (faint dashed line at x = P_x) ----
n_dash = 30;
dash_span = 160;
for (i = [0 : n_dash - 1]) {
        if (i % 2 == 0) {
                y_pos = -dash_span/2 + i * (dash_span / n_dash);
                color([0.50, 0.50, 0.55, 0.35])
                        translate([P_x, y_pos, z_base + base_t/2 + 0.3])
                                cube([0.6, dash_span / n_dash * 0.7, 0.3], center=true);
        }
}

// ---- A's circular path (faint dotted circle) ----
n_circle = 120;
for (i = [0 : n_circle - 1]) {
        frac = i / n_circle;
        // Map to operating range [50, 310] degrees
        circ_theta = 50 + frac * 260;
        cx = -d + d * cos(circ_theta);
        cy = d * sin(circ_theta);
        color([0.85, 0.35, 0.35, 0.25])
                translate([cx, cy, z_base + base_t/2 + 0.2])
                        cylinder(h=0.2, r=0.5, $fn=8);
}

// ---- Straight-line trail (dots where P has been) ----
n_trail = 60;
for (i = [0 : n_trail - 1]) {
        t_i = i / n_trail;
        trail_theta = 50 + t_i * 260;
        trail_Ay = d * sin(trail_theta);
        trail_Ax = -d + d * cos(trail_theta);
        trail_OAsq = trail_Ax*trail_Ax + trail_Ay*trail_Ay;
        trail_k = inv_k / trail_OAsq;
        trail_Py = trail_k * trail_Ay;

        // Fade: dots behind current position are brighter
        dt = $t - t_i;
        fade_t = dt - floor(dt);
        brightness = 0.3 + 0.7 * (1 - fade_t);

        color([trail_color[0] * brightness, trail_color[1] * brightness,
               trail_color[2] * brightness])
                translate([P_x, trail_Py, z_base + base_t/2 + 0.3])
                        cylinder(h=0.4, r=1.2, $fn=10);
}

// ---- Ground bar: O <-> O' (bar 1) ----
link_between(O_x, O_y, Op_x, Op_y, z_ground, ground_color);

// ---- Crank: O' -> A (bar 2) ----
link_between(Op_x, Op_y, A_x, A_y, z_crank, crank_color);

// ---- Long link 1: O -> B (bar 3) ----
link_between(O_x, O_y, B_x, B_y, z_long, long_color);

// ---- Long link 2: O -> C (bar 4) ----
link_between(O_x, O_y, C_x, C_y, z_long, long_color);

// ---- Rhombus link: A -> B (bar 5) ----
link_between(A_x, A_y, B_x, B_y, z_rhombus, rhombus_color);

// ---- Rhombus link: B -> P (bar 6) ----
link_between(B_x, B_y, P_x, P_y, z_rhombus, rhombus_color);

// ---- Rhombus link: P -> C (bar 7) ----
link_between(P_x, P_y, C_x, C_y, z_rhombus, rhombus_color);

// ---- Rhombus link: C -> A (bar 8) ----
link_between(C_x, C_y, A_x, A_y, z_rhombus, rhombus_color);

// ---- Joint pins ----
// O: ground + long links
joint_pin(O_x, O_y, z_ground, z_long);

// O': ground + crank
joint_pin(Op_x, Op_y, z_ground, z_crank);

// A: crank + rhombus
joint_pin(A_x, A_y, z_crank, z_rhombus);

// B: long link + rhombus
joint_pin(B_x, B_y, z_long, z_rhombus);

// C: long link + rhombus
joint_pin(C_x, C_y, z_long, z_rhombus);

// P: output point — gold marker + pin
joint_pin(P_x, P_y, z_rhombus, z_rhombus);

// ---- Output point P (gold marker) ----
translate([P_x, P_y, z_rhombus]) {
        color(output_color)
                cylinder(h=thickness + 4, r=pin_r + 1.5, center=true, $fn=24);
        // Decorative ring
        color([0.85, 0.65, 0.05])
                translate([0, 0, thickness/2 + 2])
                        cylinder(h=2, r=pin_r + 2.5, center=true, $fn=24);
}

// ---- Joint labels ----
point_label(O_x,  O_y,  z_long,    "O",   8,   6);
point_label(Op_x, Op_y, z_crank,   "O'", -10,  6);
point_label(A_x,  A_y,  z_rhombus, "A",   8,   6);
point_label(B_x,  B_y,  z_rhombus, "B",   8,   6);
point_label(C_x,  C_y,  z_rhombus, "C",   8,  -8);
point_label(P_x,  P_y,  z_rhombus, "P",  -10,  0);

// ---- Angle indicator (arc showing theta from crank pivot O') ----
color([0.9, 0.3, 0.3, 0.6]) {
        n_arc = max(1, floor(($t) * 26));
        arc_r = 15;
        for (i = [0 : n_arc - 1]) {
                a1 = 50 + i * 10;
                ax = Op_x + arc_r * cos(a1);
                ay = Op_y + arc_r * sin(a1);
                translate([ax, ay, z_crank + thickness/2 + 1])
                        sphere(r=0.7, $fn=10);
        }
}

// ---- Angle label ----
color([0.90, 0.40, 0.40])
        translate([Op_x + 20, Op_y + 18, z_crank + thickness/2 + 2])
                text(str("θ=", floor(theta), "°"), size=4.5, halign="left",
                     font="Liberation Sans");

// ---- "x = const" label near the vertical guide ----
color([0.70, 0.70, 0.75])
        translate([P_x - 18, -dash_span/2 + 5, z_base + base_t/2 + 1])
                rotate([0, 0, 90])
                        text("x = -36.9 (constant)", size=4, halign="left",
                             font="Liberation Sans");
