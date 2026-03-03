// Double Slider-Crank Mechanism (Elliptic Trammel / Ellipsograph)
// Uses $t (0..1) for one full revolution
// Two perpendicular slider guides connected by a rigid link
// A tracer point on the link traces an ellipse

// ---- Parameters ----
link_len    = 100;          // connecting link length (mm)
tracer_frac = 0.35;         // tracer position along link (0=slider1, 1=slider2)
thickness   = 6;            // link/component thickness
link_w      = 10;           // link width
pin_r       = 3;            // pin/joint radius
slider_w    = 22;           // slider block width
slider_h    = 14;           // slider block height (rail direction)
rail_len    = 130;          // rail half-length
base_side   = 300;          // base plate side
base_t      = 4;            // base plate thickness
groove_w    = 26;           // groove width in base
groove_d    = 3;            // groove depth

// ---- Kinematics ----
theta = $t * 360;

// Slider 1 on x-axis
s1_x = link_len * cos(theta);
s1_y = 0;

// Slider 2 on y-axis
s2_x = 0;
s2_y = link_len * sin(theta);

// Link angle (from slider1 to slider2)
link_angle = atan2(s2_y - s1_y, s2_x - s1_x);

// Tracer point on the link
tracer_x = s1_x + tracer_frac * (s2_x - s1_x);
tracer_y = s1_y + tracer_frac * (s2_y - s1_y);

// Ellipse semi-axes traced by the point
semi_a = link_len * (1 - tracer_frac);   // x semi-axis = 65
semi_b = link_len * tracer_frac;          // y semi-axis = 35

// ---- Z Layers ----
z_base   = -base_t/2 - 2;
z_slider = 2;                        // slider blocks
z_link   = z_slider + thickness + 2; // link above sliders

// ---- Colors ----
link_color    = [0.25, 0.55, 0.85];   // blue
s1_color      = [0.85, 0.25, 0.25];   // red
s2_color      = [0.30, 0.75, 0.35];   // green
pin_color     = [0.90, 0.90, 0.90];   // silver
base_color    = [0.35, 0.35, 0.40];   // dark gray
rail_color    = [0.55, 0.55, 0.58];   // medium gray
tracer_color  = [0.95, 0.75, 0.10];   // gold
trail_color   = [0.90, 0.65, 0.10];   // warm gold
groove_color  = [0.28, 0.28, 0.33];   // darker than base

// ---- Modules ----
module rounded_link(length, width, thick) {
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

// ---- Base plate ----
color(base_color)
    translate([0, 0, z_base])
        cube([base_side, base_side, base_t], center=true);

// ---- Groove channels in base (recessed tracks) ----
// X-axis groove
color(groove_color)
    translate([0, 0, z_base + base_t/2 + groove_d/2])
        cube([rail_len * 2 + 20, groove_w, groove_d], center=true);

// Y-axis groove
color(groove_color)
    translate([0, 0, z_base + base_t/2 + groove_d/2])
        cube([groove_w, rail_len * 2 + 20, groove_d], center=true);

// ---- Rail guide edges ----
// X-axis rails (top/bottom edges of groove)
color(rail_color) {
    translate([0,  groove_w/2 + 1, z_slider])
        cube([rail_len * 2 + 20, 2, thickness], center=true);
    translate([0, -groove_w/2 - 1, z_slider])
        cube([rail_len * 2 + 20, 2, thickness], center=true);
}

// Y-axis rails (left/right edges of groove)
color(rail_color) {
    translate([ groove_w/2 + 1, 0, z_slider])
        cube([2, rail_len * 2 + 20, thickness], center=true);
    translate([-groove_w/2 - 1, 0, z_slider])
        cube([2, rail_len * 2 + 20, thickness], center=true);
}

// ---- Rail end caps ----
color(rail_color) {
    // X-axis ends
    translate([ rail_len + 10, 0, z_slider])
        cube([4, groove_w + 6, thickness], center=true);
    translate([-rail_len - 10, 0, z_slider])
        cube([4, groove_w + 6, thickness], center=true);
    // Y-axis ends
    translate([0,  rail_len + 10, z_slider])
        cube([groove_w + 6, 4, thickness], center=true);
    translate([0, -rail_len - 10, z_slider])
        cube([groove_w + 6, 4, thickness], center=true);
}

// ---- Axis labels ----
color([0.75, 0.75, 0.75]) {
    translate([rail_len + 20, 0, z_slider + thickness/2 + 1])
        text("X", size=8, halign="center", valign="center", font="Liberation Sans:style=Bold");
    translate([0, rail_len + 20, z_slider + thickness/2 + 1])
        text("Y", size=8, halign="center", valign="center", font="Liberation Sans:style=Bold");
}

// ---- Slider 1 (x-axis, red) ----
translate([s1_x, 0, z_slider]) {
    color(s1_color)
        difference() {
            cube([slider_w, slider_w, slider_h], center=true);
            // Pin bore
            cylinder(h=slider_h+2, r=pin_r+0.5, center=true, $fn=24);
        }
    // Pin shaft (extends up to link level)
    pin_shaft(slider_h + thickness + 8);
}

// ---- Slider 2 (y-axis, green) ----
translate([0, s2_y, z_slider]) {
    color(s2_color)
        difference() {
            cube([slider_w, slider_w, slider_h], center=true);
            // Pin bore
            cylinder(h=slider_h+2, r=pin_r+0.5, center=true, $fn=24);
        }
    // Pin shaft
    pin_shaft(slider_h + thickness + 8);
}

// ---- Connecting link (blue) ----
translate([s1_x, s1_y, z_link])
    rotate([0, 0, link_angle]) {
        color(link_color)
            difference() {
                rounded_link(link_len, link_w, thickness);
                // Bore at slider 1 end
                joint_bore(thickness);
                // Bore at slider 2 end
                translate([link_len, 0, 0])
                    joint_bore(thickness);
                // Bore at tracer point
                translate([tracer_frac * link_len, 0, 0])
                    joint_bore(thickness);
            }
    }

// ---- Tracer tool (gold pen) ----
translate([tracer_x, tracer_y, 0]) {
    // Upper shaft
    color(tracer_color)
        translate([0, 0, z_link])
            cylinder(h=thickness + 6, r=pin_r + 1.5, center=true, $fn=24);
    // Decorative ring
    color([0.85, 0.65, 0.05])
        translate([0, 0, z_link + thickness/2 + 2])
            cylinder(h=2, r=pin_r + 2.5, center=true, $fn=24);
    // Pen tip pointing down
    color([0.15, 0.15, 0.15])
        translate([0, 0, z_base + base_t/2 + 2])
            cylinder(h=4, r1=0.8, r2=pin_r + 1, center=true, $fn=16);
    // Ink dot at current position
    color(tracer_color)
        translate([0, 0, z_base + base_t/2 + 0.3])
            cylinder(h=0.5, r=1.5, $fn=12);
}

// ---- Ellipse trail (traced path) ----
n_trail = 90;
for (i = [0 : n_trail - 1]) {
    t_i = i / n_trail;
    ang = t_i * 360;
    // Points on the ellipse
    tx = semi_a * cos(ang);
    ty = semi_b * sin(ang);

    // Fade: dots behind current position are brighter
    dt = $t - t_i;
    fade_t = dt - floor(dt);   // 0..1, how far behind
    brightness = 0.3 + 0.7 * (1 - fade_t);

    color([trail_color[0] * brightness, trail_color[1] * brightness, trail_color[2] * brightness])
        translate([tx, ty, z_base + base_t/2 + 0.2])
            cylinder(h=0.3, r=1.0, $fn=10);
}

// ---- Faint full ellipse outline ----
n_outline = 180;
for (i = [0 : n_outline - 1]) {
    ang = i * 360 / n_outline;
    ex = semi_a * cos(ang);
    ey = semi_b * sin(ang);
    color([0.5, 0.5, 0.5, 0.3])
        translate([ex, ey, z_base + base_t/2 + 0.1])
            cylinder(h=0.2, r=0.4, $fn=8);
}

// ---- Semi-axis dimension lines ----
// a-axis (x)
color([0.8, 0.3, 0.3, 0.6])
    translate([semi_a/2, -semi_b - 12, z_base + base_t/2 + 0.5])
        cube([semi_a, 0.8, 0.5], center=true);
color([0.9, 0.4, 0.4])
    translate([semi_a/2, -semi_b - 18, z_base + base_t/2 + 1])
        text("a = 65", size=5, halign="center", font="Liberation Sans");

// b-axis (y)
color([0.3, 0.7, 0.3, 0.6])
    translate([-semi_a - 12, semi_b/2, z_base + base_t/2 + 0.5])
        cube([0.8, semi_b, 0.5], center=true);
color([0.4, 0.8, 0.4])
    translate([-semi_a - 18, semi_b/2, z_base + base_t/2 + 1])
        rotate([0, 0, 90])
            text("b = 35", size=5, halign="center", font="Liberation Sans");

// ---- Origin cross-hair ----
color([0.8, 0.8, 0.8]) {
    translate([0, 0, z_base + base_t/2 + groove_d + 0.5])
        cylinder(h=1, r=4, center=true, $fn=32);
    translate([0, 0, z_base + base_t/2 + groove_d + 1.2])
        cylinder(h=0.5, r=2, center=true, $fn=24);
}

// ---- Title ----
color([0.85, 0.85, 0.85])
    translate([0, base_side/2 - 20, z_base + base_t/2 + 0.5])
        text("Double Slider-Crank (Elliptic Trammel)", size=7,
             halign="center", font="Liberation Sans:style=Bold");

// ---- Subtitle ----
color([0.65, 0.65, 0.65])
    translate([0, -base_side/2 + 12, z_base + base_t/2 + 0.5])
        text("Ellipsograph — traces ellipse with semi-axes a, b",
             size=5, halign="center", font="Liberation Sans");

// ---- Angle indicator (arc showing theta) ----
color([0.9, 0.9, 0.3, 0.7]) {
    n_arc = floor($t * 36);
    arc_r = 20;
    for (i = [0 : max(0, n_arc - 1)]) {
        a1 = i * 10;
        ax = arc_r * cos(a1);
        ay = arc_r * sin(a1);
        translate([ax, ay, z_link + thickness/2 + 1])
            sphere(r=0.8, $fn=10);
    }
}

// ---- Angle label ----
color([0.9, 0.9, 0.3])
    translate([28, 28, z_link + thickness/2 + 2])
        text(str("θ = ", floor(theta), "°"), size=5, halign="left",
             font="Liberation Sans");
