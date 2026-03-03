// Ball-on-Plate Balancing Mechanism
// Uses $t (0..1) for a complete balancing demonstration
// A 2-DOF tilting plate controlled by two servo actuators
// balances a rolling ball that follows a figure-8 trajectory

// ---- Parameters ----
plate_side  = 120;          // plate width/depth (mm)
plate_t     = 3;            // plate thickness
plate_r     = 4;            // plate corner radius
ball_r      = 8;            // ball radius
base_h      = 50;           // base/pedestal height
base_w      = 140;          // base width
base_d      = 140;          // base depth
base_t      = 5;            // base plate thickness
pillar_r    = 6;            // support pillar radius
gimbal_r    = 8;            // gimbal ring radius
servo_w     = 12;           // servo body width
servo_l     = 24;           // servo body length
servo_h     = 10;           // servo body height
pushrod_r   = 1.5;          // pushrod radius
pushrod_ball_r = 3;         // pushrod ball joint radius
link_arm    = 18;           // servo horn arm length

// ---- Motion ----
// Ball follows figure-8 (lissajous) on the plate
// Plate tilts to "steer" the ball via gravity
cycle = $t * 360;

// Ball position on plate (relative to plate center)
ball_amp_x = 35;
ball_amp_y = 25;
ball_x = ball_amp_x * sin(2 * cycle);
ball_y = ball_amp_y * sin(cycle);

// Plate tilt angles (proportional to ball acceleration / position offset)
// Tilt to keep ball on the figure-8: tilt opposite to desired acceleration
max_tilt = 8;   // degrees
tilt_x = -max_tilt * sin(cycle) * 0.7;           // roll (around Y axis)
tilt_y =  max_tilt * cos(2 * cycle) * 0.6;       // pitch (around X axis)

// Servo horn angles (map plate tilt to servo rotation)
servo1_angle = tilt_x * 2.5;   // X-axis servo
servo2_angle = tilt_y * 2.5;   // Y-axis servo

// ---- Smoothstep for trail fade ----
function smooth01(t) = t * t * (3 - 2 * t);

// ---- Colors ----
plate_color     = [0.75, 0.78, 0.82];    // light aluminum
plate_edge      = [0.60, 0.62, 0.66];
ball_color      = [0.90, 0.25, 0.20];    // red ball
ball_highlight  = [1.00, 0.50, 0.45];
base_color      = [0.25, 0.25, 0.28];    // dark base
pillar_color    = [0.55, 0.55, 0.58];    // steel pillars
gimbal_color    = [0.45, 0.48, 0.52];    // gimbal ring
servo_color     = [0.15, 0.15, 0.18];    // black servo
servo_label     = [0.85, 0.75, 0.10];    // yellow label
horn_color      = [0.80, 0.80, 0.82];    // white horn
pushrod_color   = [0.70, 0.70, 0.72];    // silver rod
joint_color     = [0.60, 0.60, 0.65];
trail_color     = [0.90, 0.40, 0.30];
ground_color    = [0.30, 0.30, 0.32];
grid_color      = [0.35, 0.35, 0.37];
target_color    = [0.20, 0.70, 0.30, 0.4];

// ---- Z positions ----
z_ground = 0;
z_base_top = base_h + base_t;
z_plate = z_base_top + 25;        // plate pivot height

// ---- Modules ----
module rounded_plate(w, d, t, r) {
    // Plate with rounded corners
    hull() {
        translate([ w/2 - r,  d/2 - r, 0]) cylinder(h=t, r=r, center=true, $fn=20);
        translate([-w/2 + r,  d/2 - r, 0]) cylinder(h=t, r=r, center=true, $fn=20);
        translate([ w/2 - r, -d/2 + r, 0]) cylinder(h=t, r=r, center=true, $fn=20);
        translate([-w/2 + r, -d/2 + r, 0]) cylinder(h=t, r=r, center=true, $fn=20);
    }
}

module servo_body() {
    // Servo case
    color(servo_color) {
        cube([servo_l, servo_w, servo_h], center=true);
        // Mounting tabs
        translate([0, 0, servo_h/2 - 1])
            cube([servo_l + 8, servo_w, 2], center=true);
    }
    // Label
    color(servo_label)
        translate([0, servo_w/2 + 0.1, 0])
            rotate([90, 0, 0])
                text("SRV", size=4, halign="center", valign="center",
                     font="Liberation Sans:style=Bold");
    // Output shaft
    color(horn_color)
        translate([servo_l/2 - 4, 0, servo_h/2])
            cylinder(h=4, r=2.5, center=true, $fn=16);
}

module servo_horn(angle) {
    rotate([0, 0, angle]) {
        color(horn_color) {
            // Horn arm
            hull() {
                cylinder(h=2, r=3.5, center=true, $fn=16);
                translate([link_arm, 0, 0])
                    cylinder(h=2, r=2, center=true, $fn=12);
            }
        }
        // Ball joint at tip
        color(joint_color)
            translate([link_arm, 0, 0])
                sphere(r=pushrod_ball_r, $fn=16);
    }
}

module pushrod(p1, p2) {
    // Rod between two 3D points
    dx = p2[0] - p1[0];
    dy = p2[1] - p1[1];
    dz = p2[2] - p1[2];
    len = sqrt(dx*dx + dy*dy + dz*dz);
    ax = atan2(sqrt(dx*dx + dy*dy), dz);
    az = atan2(dy, dx);

    color(pushrod_color)
    translate(p1)
        rotate([0, 0, az])
            rotate([ax, 0, 0])
                cylinder(h=len, r=pushrod_r, $fn=12);
    // Ball joints at each end
    color(joint_color) {
        translate(p1) sphere(r=pushrod_ball_r, $fn=14);
        translate(p2) sphere(r=pushrod_ball_r, $fn=14);
    }
}

// ========================================
// ---- Scene ----
// ========================================

// ---- Ground ----
color(ground_color)
    translate([0, 0, -1])
        cube([300, 300, 2], center=true);

// Grid
color(grid_color)
for (gx = [-140 : 20 : 140])
    translate([gx, 0, 0.1])
        cube([0.3, 300, 0.2], center=true);
color(grid_color)
for (gy = [-140 : 20 : 140])
    translate([0, gy, 0.1])
        cube([300, 0.3, 0.2], center=true);

// ---- Base / Pedestal ----
// Main box
color(base_color) {
    translate([0, 0, base_t/2])
        cube([base_w, base_d, base_t], center=true);
    // Vertical frame
    translate([0, 0, base_h/2 + base_t])
        cube([base_w - 20, base_d - 20, base_h], center=true);
    // Top plate
    translate([0, 0, z_base_top - base_t/2])
        cube([base_w - 10, base_d - 10, base_t], center=true);
}

// Corner pillars
color(pillar_color)
for (sx = [-1, 1])
    for (sy = [-1, 1])
        translate([sx * (base_w/2 - 10), sy * (base_d/2 - 10), base_h/2 + base_t])
            cylinder(h=base_h, r=pillar_r, center=true, $fn=20);

// ---- Servo 1 (X-axis tilt, front) ----
translate([0, -base_d/2 + 18, z_base_top + 5]) {
    rotate([0, 0, 0])
        servo_body();
    // Horn
    translate([servo_l/2 - 4, 0, servo_h/2 + 2])
        rotate([0, 0, 90])
            servo_horn(servo1_angle);
}

// ---- Servo 2 (Y-axis tilt, right side) ----
translate([base_w/2 - 18, 0, z_base_top + 5]) {
    rotate([0, 0, 90])
        servo_body();
    // Horn
    translate([0, -(servo_l/2 - 4), servo_h/2 + 2])
        servo_horn(servo2_angle);
}

// ---- Central gimbal / universal joint ----
translate([0, 0, z_plate]) {
    // Outer gimbal ring (X rotation)
    color(gimbal_color)
        rotate([tilt_y, 0, 0])
            difference() {
                cylinder(h=4, r=gimbal_r + 3, center=true, $fn=32);
                cylinder(h=5, r=gimbal_r, center=true, $fn=32);
            }
    // Inner pivot post
    color(pillar_color)
        cylinder(h=20, r=4, center=true, $fn=20);
    // Pivot ball
    color(joint_color)
        sphere(r=5, $fn=24);
}

// ---- Support column (base to gimbal) ----
color(pillar_color)
    translate([0, 0, z_base_top + 12])
        cylinder(h=24, r=5, center=true, $fn=24);

// ---- Tilting plate ----
translate([0, 0, z_plate])
    rotate([tilt_y, tilt_x, 0]) {
        // Plate surface
        color(plate_color)
            rounded_plate(plate_side, plate_side, plate_t, plate_r);

        // Plate edge bevel
        color(plate_edge)
            difference() {
                rounded_plate(plate_side + 1, plate_side + 1, plate_t - 1, plate_r + 0.5);
                rounded_plate(plate_side - 2, plate_side - 2, plate_t + 1, plate_r);
            }

        // Grid lines on plate surface
        color([0.65, 0.68, 0.72])
        for (gx = [-50 : 10 : 50])
            translate([gx, 0, plate_t/2 + 0.1])
                cube([0.3, plate_side - 8, 0.1], center=true);
        color([0.65, 0.68, 0.72])
        for (gy = [-50 : 10 : 50])
            translate([0, gy, plate_t/2 + 0.1])
                cube([plate_side - 8, 0.3, 0.1], center=true);

        // Center cross-hair
        color([0.40, 0.42, 0.48]) {
            translate([0, 0, plate_t/2 + 0.15])
                cube([plate_side * 0.7, 0.8, 0.15], center=true);
            translate([0, 0, plate_t/2 + 0.15])
                cube([0.8, plate_side * 0.7, 0.15], center=true);
        }
        // Center circle
        color([0.40, 0.42, 0.48])
            translate([0, 0, plate_t/2 + 0.15])
                difference() {
                    cylinder(h=0.15, r=12, center=true, $fn=32);
                    cylinder(h=0.3, r=11, center=true, $fn=32);
                }

        // ---- Target figure-8 path on plate ----
        n_path = 120;
        for (i = [0 : n_path - 1]) {
            a = i * 360 / n_path;
            tx = ball_amp_x * sin(2 * a);
            ty = ball_amp_y * sin(a);
            color([target_color[0], target_color[1], target_color[2], 0.3])
                translate([tx, ty, plate_t/2 + 0.1])
                    cylinder(h=0.15, r=0.8, $fn=8);
        }

        // ---- Ball trail (recent positions) ----
        n_trail = 30;
        for (i = [0 : n_trail - 1]) {
            t_i = ($t - (n_trail - i) * 0.008);
            t_wrapped = t_i - floor(t_i);
            a_trail = t_wrapped * 360;
            bx = ball_amp_x * sin(2 * a_trail);
            by = ball_amp_y * sin(a_trail);
            fade = (i + 1) / n_trail;
            color([trail_color[0] * fade, trail_color[1] * fade, trail_color[2] * fade, fade * 0.6])
                translate([bx, by, plate_t/2 + 0.1])
                    cylinder(h=0.2, r=1.2 * fade, $fn=8);
        }

        // ---- The Ball ----
        translate([ball_x, ball_y, plate_t/2 + ball_r]) {
            // Ball body
            color(ball_color)
                sphere(r=ball_r, $fn=32);
            // Highlight
            color(ball_highlight)
                translate([ball_r * 0.3, -ball_r * 0.3, ball_r * 0.4])
                    sphere(r=ball_r * 0.3, $fn=16);
            // Shadow on plate (projected down)
            color([0.3, 0.3, 0.35, 0.4])
                translate([0, 0, -(ball_r - 0.2)])
                    cylinder(h=0.2, r=ball_r * 0.9, $fn=20);
        }

        // ---- Plate attachment points for pushrods ----
        // Front attachment (servo 1)
        color(joint_color)
            translate([0, -plate_side/2 + 5, -plate_t/2])
                sphere(r=pushrod_ball_r, $fn=14);
        // Right attachment (servo 2)
        color(joint_color)
            translate([plate_side/2 - 5, 0, -plate_t/2])
                sphere(r=pushrod_ball_r, $fn=14);
    }

// ---- Pushrods (connecting servos to plate) ----
// Compute pushrod endpoints
// Servo 1 horn tip (approximate)
s1_horn_x = 0 + link_arm * sin(servo1_angle * 3.14159/180);
s1_horn_y = -base_d/2 + 18 + (servo_l/2 - 4);
s1_horn_z = z_base_top + 5 + servo_h/2 + 2;

// Plate front attachment (with tilt applied — approximate)
p1_x = 0;
p1_y = -plate_side/2 + 5;
p1_z = z_plate - plate_t/2;
// Apply small tilt correction
p1_y_tilted = p1_y * cos(tilt_y) + p1_z * sin(tilt_y) - z_plate * sin(tilt_y);
p1_z_tilted = z_plate + (-p1_y * sin(tilt_y) + (p1_z - z_plate) * cos(tilt_y));

pushrod([s1_horn_x, s1_horn_y, s1_horn_z],
        [p1_x, -plate_side/2 + 5 + tilt_y * 0.3, z_plate - 2]);

// Servo 2 horn tip
s2_horn_x = base_w/2 - 18 + link_arm * cos(servo2_angle * 3.14159/180);
s2_horn_y = 0 + link_arm * sin(servo2_angle * 3.14159/180);
s2_horn_z = z_base_top + 5 + servo_h/2 + 2;

pushrod([s2_horn_x, s2_horn_y, s2_horn_z],
        [plate_side/2 - 5 + tilt_x * 0.3, 0, z_plate - 2]);

// ---- Sensor (camera/vision above plate) ----
// Camera mount post
color(pillar_color)
    translate([-base_w/2 + 5, -base_d/2 + 5, base_h/2 + base_t])
        cylinder(h=base_h + 40, r=3, center=true, $fn=16);

// Camera arm
color(pillar_color)
    translate([-base_w/2 + 5 + 35, -base_d/2 + 5 + 35, base_h + base_t + 35])
        rotate([0, 45, 45])
            cube([70, 4, 4], center=true);

// Camera
translate([0, 0, z_plate + 60]) {
    color(servo_color)
        cube([14, 14, 10], center=true);
    // Lens (pointing down)
    color([0.15, 0.15, 0.45])
        translate([0, 0, -6])
            cylinder(h=3, r=5, center=true, $fn=24);
    color([0.10, 0.10, 0.30])
        translate([0, 0, -8])
            cylinder(h=1, r=4, center=true, $fn=24);
    // LED indicator
    led_blink = sin($t * 360 * 6) > 0 ? 1.0 : 0.3;
    color([0.1 * led_blink, 0.9 * led_blink, 0.1 * led_blink])
        translate([6, 0, 3])
            sphere(r=1.2, $fn=10);
    // Label
    color([0.7, 0.7, 0.7])
        translate([0, 7.5, 0])
            rotate([90, 0, 0])
                text("CAM", size=4, halign="center", valign="center",
                     font="Liberation Sans:style=Bold");
}

// ---- Control signal visualization (sine waves on base) ----
// X-axis signal
color([0.3, 0.7, 0.9])
for (i = [0:39]) {
    sx = -base_w/2 + 10 + i * 3;
    sy_sig = -base_d/2 + 8 + 5 * sin(i * 18 + cycle);
    translate([sx, sy_sig, base_t + 1])
        sphere(r=0.6, $fn=8);
}

// Y-axis signal
color([0.9, 0.5, 0.2])
for (i = [0:39]) {
    sy = -base_d/2 + 10 + i * 3;
    sx_sig = -base_w/2 + 8 + 5 * sin(i * 9 + cycle * 2);
    translate([sx_sig, sy, base_t + 1])
        sphere(r=0.6, $fn=8);
}

// ---- Title ----
color([0.85, 0.85, 0.85])
    translate([0, -base_d/2 - 30, 0.5])
        text("Ball-on-Plate Balancing System", size=8,
             halign="center", font="Liberation Sans:style=Bold");

// ---- Subtitle ----
color([0.65, 0.65, 0.65])
    translate([0, base_d/2 + 20, 0.5])
        text("2-DOF PID Control  |  Vision Feedback  |  Figure-8 Tracking",
             size=5, halign="center", font="Liberation Sans");

// ---- Axis labels on plate ----
translate([0, 0, z_plate])
    rotate([tilt_y, tilt_x, 0]) {
        color([0.5, 0.5, 0.55])
            translate([plate_side/2 - 8, -plate_side/2 + 6, plate_t/2 + 0.5])
                text("X", size=6, font="Liberation Sans:style=Bold");
        color([0.5, 0.5, 0.55])
            translate([-plate_side/2 + 4, plate_side/2 - 12, plate_t/2 + 0.5])
                text("Y", size=6, font="Liberation Sans:style=Bold");
    }

// ---- Error display (distance from setpoint) ----
error_dist = sqrt(ball_x * ball_x + ball_y * ball_y);
error_color = error_dist < 15 ? [0.2, 0.8, 0.3] :
              error_dist < 30 ? [0.9, 0.8, 0.2] : [0.9, 0.3, 0.2];
color(error_color)
    translate([base_w/2 + 20, -20, 0.5])
        text("TRACKING", size=5, halign="left",
             font="Liberation Sans:style=Bold");
color([0.7, 0.7, 0.7])
    translate([base_w/2 + 20, -30, 0.5])
        text(str("Tilt X: ", round(tilt_x*10)/10, "°"), size=4,
             halign="left", font="Liberation Sans");
color([0.7, 0.7, 0.7])
    translate([base_w/2 + 20, -38, 0.5])
        text(str("Tilt Y: ", round(tilt_y*10)/10, "°"), size=4,
             halign="left", font="Liberation Sans");
