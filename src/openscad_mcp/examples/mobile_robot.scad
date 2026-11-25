// Mobile Robot Animation — Differential Drive with Sensor Suite
// Uses $t (0..1) for a complete navigation sequence:
//   Phase 1 (0.00–0.30): Drive forward along path
//   Phase 2 (0.30–0.45): Turn left 90°
//   Phase 3 (0.45–0.70): Drive forward
//   Phase 4 (0.70–0.85): Turn right 45°
//   Phase 5 (0.85–1.00): Drive forward to goal

// ---- Parameters ----
body_l     = 50;       // chassis length
body_w     = 36;       // chassis width
body_h     = 12;       // chassis height
wheel_r    = 10;       // wheel radius
wheel_w    = 5;        // wheel width
caster_r   = 4;        // rear caster radius
axle_r     = 1.5;      // axle radius
bumper_t   = 3;        // bumper thickness

lidar_r    = 8;        // LiDAR dome radius
lidar_h    = 6;        // LiDAR height
cam_w      = 10;       // camera module width
cam_h      = 8;        // camera height
cam_d      = 6;        // camera depth

// ---- Smoothstep ----
function smooth(t) = t * t * (3 - 2 * t);
function clamp01(t) = min(1, max(0, t));
function smoothstep(t, a, b) = smooth(clamp01((t - a) / (b - a)));

// ---- Path definition ----
// Waypoints: [x, y, heading_deg]
// Phase 1: start (0,0,0) → (120,0,0)         drive forward
// Phase 2: turn at (120,0) from 0° to 90°     turn left
// Phase 3: (120,0,90) → (120,100,90)          drive forward
// Phase 4: turn at (120,100) from 90° to 45°  turn right
// Phase 5: (120,100,45) → (190,170,45)        drive forward to goal

// Segment lengths for wheel spin calculation
seg1_len = 120;
seg3_len = 100;
seg5_len = 99;   // sqrt(70^2 + 70^2) ≈ 99

function robot_pos(t) =
    // Phase 1: drive forward (0→120, 0)
    t < 0.30 ? let(f = smoothstep(t, 0.0, 0.30))
        [f * seg1_len, 0, 0]
    // Phase 2: turn left 90° at (120, 0)
    : t < 0.45 ? let(f = smoothstep(t, 0.30, 0.45))
        [seg1_len, 0, f * 90]
    // Phase 3: drive forward (120, 0→100)
    : t < 0.70 ? let(f = smoothstep(t, 0.45, 0.70))
        [seg1_len, f * seg3_len, 90]
    // Phase 4: turn right 45° at (120, 100)
    : t < 0.85 ? let(f = smoothstep(t, 0.70, 0.85))
        [seg1_len, seg3_len, 90 - f * 45]
    // Phase 5: drive forward at 45°
    : let(f = smoothstep(t, 0.85, 1.0))
        [seg1_len + f * 70, seg3_len + f * 70, 45];

// Current robot state
rx    = robot_pos($t)[0];
ry    = robot_pos($t)[1];
rhead = robot_pos($t)[2];

// Cumulative wheel rotation (approximate distance traveled)
wheel_spin = ($t < 0.30 ? smoothstep($t, 0, 0.30) * seg1_len :
              $t < 0.45 ? seg1_len :
              $t < 0.70 ? seg1_len + smoothstep($t, 0.45, 0.70) * seg3_len :
              $t < 0.85 ? seg1_len + seg3_len :
              seg1_len + seg3_len + smoothstep($t, 0.85, 1.0) * seg5_len)
             / (2 * 3.14159 * wheel_r) * 360;

// ---- Colors ----
chassis_color  = [0.15, 0.15, 0.18];   // dark charcoal
top_color      = [0.22, 0.22, 0.26];   // slightly lighter
wheel_color    = [0.10, 0.10, 0.10];   // black
tire_color     = [0.20, 0.20, 0.22];
hub_color      = [0.70, 0.70, 0.72];   // silver hub
bumper_color   = [0.80, 0.25, 0.20];   // red bumper
lidar_color    = [0.25, 0.25, 0.28];   // dark
lidar_lens     = [0.10, 0.40, 0.80];   // blue lens
cam_color      = [0.20, 0.20, 0.22];
cam_lens_color = [0.15, 0.15, 0.50];
led_green      = [0.1, 0.95, 0.2];
led_blue       = [0.1, 0.4, 0.95];
antenna_color  = [0.50, 0.50, 0.52];
ground_color   = [0.30, 0.32, 0.28];
grid_color     = [0.35, 0.37, 0.33];
path_color     = [0.20, 0.60, 0.90, 0.7];
goal_color     = [0.90, 0.30, 0.25];
start_color    = [0.30, 0.80, 0.35];

// ---- Modules ----
module wheel() {
    rotate([0, wheel_spin, 0])
    rotate([90, 0, 0]) {
        // Tire
        color(tire_color)
            cylinder(h=wheel_w, r=wheel_r, center=true, $fn=32);
        // Hub cap
        color(hub_color)
            cylinder(h=wheel_w + 0.5, r=wheel_r * 0.45, center=true, $fn=24);
        // Tread marks (6 grooves)
        color([0.08, 0.08, 0.08])
        for (i = [0:5])
            rotate([0, 0, i * 60])
                translate([wheel_r - 0.5, 0, 0])
                    cube([1.5, 1.5, wheel_w + 0.2], center=true);
    }
}

module caster() {
    // Caster housing
    color(hub_color)
        cylinder(h=6, r=caster_r + 2, center=true, $fn=24);
    // Caster ball
    color(tire_color)
        translate([0, 0, -3])
            sphere(r=caster_r, $fn=20);
}

module lidar_unit() {
    // Base
    color(lidar_color)
        cylinder(h=3, r=lidar_r, center=true, $fn=32);
    // Spinning dome
    lidar_spin = $t * 360 * 8;   // 8 full rotations
    translate([0, 0, 3])
    rotate([0, 0, lidar_spin]) {
        color(lidar_color)
            cylinder(h=lidar_h, r=lidar_r - 1, center=true, $fn=32);
        // Lens window (spinning beam indicator)
        color(lidar_lens)
            translate([lidar_r - 1.5, 0, 0])
                cube([1.5, 4, lidar_h - 1], center=true);
    }
    // Top cap
    color(hub_color)
        translate([0, 0, lidar_h/2 + 3])
            cylinder(h=1.5, r=3, center=true, $fn=20);
}

module camera() {
    // Body
    color(cam_color)
        cube([cam_d, cam_w, cam_h], center=true);
    // Lens
    color(cam_lens_color)
        translate([cam_d/2, 0, 0])
            rotate([0, 90, 0])
                cylinder(h=2, r=3, center=true, $fn=24);
    // Lens glass
    color([0.2, 0.2, 0.3])
        translate([cam_d/2 + 1, 0, 0])
            rotate([0, 90, 0])
                cylinder(h=0.5, r=2.5, center=true, $fn=24);
}

module antenna() {
    color(antenna_color) {
        cylinder(h=20, r=1, center=true, $fn=12);
        translate([0, 0, 10])
            sphere(r=2, $fn=16);
    }
}

module robot() {
    // ---- Chassis ----
    // Lower body
    color(chassis_color)
        translate([0, 0, wheel_r])
            cube([body_l, body_w, body_h], center=true);

    // Upper deck
    color(top_color)
        translate([0, 0, wheel_r + body_h/2 + 1.5])
            cube([body_l - 6, body_w - 4, 3], center=true);

    // ---- Front bumper ----
    color(bumper_color)
        translate([body_l/2 + bumper_t/2, 0, wheel_r - 1])
            cube([bumper_t, body_w + 4, body_h - 2], center=true);

    // ---- Wheels (differential drive) ----
    // Left wheel
    translate([0, body_w/2 + wheel_w/2 + 1, wheel_r])
        wheel();
    // Right wheel
    translate([0, -(body_w/2 + wheel_w/2 + 1), wheel_r])
        wheel();

    // ---- Axles ----
    color(hub_color)
        translate([0, 0, wheel_r])
            rotate([90, 0, 0])
                cylinder(h=body_w + 2*wheel_w + 6, r=axle_r, center=true, $fn=16);

    // ---- Rear caster ----
    translate([-body_l/2 + 8, 0, caster_r + 1])
        caster();

    // ---- LiDAR (top center) ----
    translate([2, 0, wheel_r + body_h/2 + 3])
        lidar_unit();

    // ---- Camera (front) ----
    translate([body_l/2 - 2, 0, wheel_r + body_h/2 + 5])
        camera();

    // ---- Antenna (rear) ----
    translate([-body_l/2 + 10, body_w/2 - 5, wheel_r + body_h/2 + 3])
        antenna();

    // ---- Status LEDs ----
    // Power LED (green, rear left)
    led_blink = sin($t * 360 * 4) > 0 ? 1.0 : 0.3;
    color([led_green[0] * led_blink, led_green[1] * led_blink, led_green[2] * led_blink])
        translate([-body_l/2 + 2, body_w/2 - 2, wheel_r + body_h/2 + 0.5])
            sphere(r=1.2, $fn=12);

    // Comms LED (blue, rear right)
    led_blink2 = sin($t * 360 * 6 + 90) > 0 ? 1.0 : 0.3;
    color([led_blue[0] * led_blink2, led_blue[1] * led_blink2, led_blue[2] * led_blink2])
        translate([-body_l/2 + 2, -(body_w/2 - 2), wheel_r + body_h/2 + 0.5])
            sphere(r=1.2, $fn=12);

    // ---- Battery indicator (3 bars on top) ----
    for (i = [0:2])
        color(i < 2 ? [0.1, 0.8, 0.2] : [0.9, 0.8, 0.1])
            translate([-body_l/2 + 18 + i*5, 0, wheel_r + body_h/2 + 3.5])
                cube([3, 8, 1.5], center=true);

    // ---- Side panels / vents ----
    color([0.18, 0.18, 0.22])
    for (side = [-1, 1])
        translate([0, side * (body_w/2 + 0.2), wheel_r])
            for (v = [-2:2])
                translate([v * 8, 0, 0])
                    cube([4, 0.5, 6], center=true);

    // ---- LiDAR scan rays (fan) ----
    lidar_angle = $t * 360 * 8;
    n_rays = 5;
    color([0.1, 0.6, 1.0, 0.15])
    for (i = [-2:2]) {
        ray_a = lidar_angle + i * 15;
        ray_len = 60 + 10 * sin(ray_a * 3);
        translate([2, 0, wheel_r + body_h/2 + 6])
            rotate([0, 0, ray_a])
                translate([ray_len/2, 0, 0])
                    cube([ray_len, 0.4, 0.4], center=true);
    }
}

// ========================================
// ---- Scene ----
// ========================================

// ---- Ground plane ----
color(ground_color)
    translate([95, 85, -1])
        cube([350, 280, 2], center=true);

// ---- Grid lines ----
color(grid_color)
for (gx = [-40 : 40 : 280])
    translate([gx, 85, 0.1])
        cube([0.5, 280, 0.2], center=true);
color(grid_color)
for (gy = [-40 : 40 : 240])
    translate([95, gy, 0.1])
        cube([350, 0.5, 0.2], center=true);

// ---- Planned path (dashed) ----
// Segment 1: (0,0) → (120,0)
for (i = [0:11])
    color(path_color)
        translate([i * 10 + 5, 0, 0.3])
            cube([6, 1.5, 0.3], center=true);

// Segment 2: turn arc at (120,0)
for (i = [0:8]) {
    a = i * 10;
    color(path_color)
        translate([120 + 8*cos(a+45), 8*sin(a+45), 0.3])
            sphere(r=0.8, $fn=8);
}

// Segment 3: (120,0) → (120,100)
for (i = [0:9])
    color(path_color)
        translate([120, i * 10 + 5, 0.3])
            cube([1.5, 6, 0.3], center=true);

// Segment 4: turn arc at (120,100)
for (i = [0:4]) {
    a = 90 - i * 10;
    color(path_color)
        translate([120 + 8*cos(a), 100 + 8*sin(a), 0.3])
            sphere(r=0.8, $fn=8);
}

// Segment 5: (120,100) → (190,170) at 45°
for (i = [0:9])
    color(path_color)
        translate([120 + i*7 + 3.5, 100 + i*7 + 3.5, 0.3])
            cube([6, 1.5, 0.3], center=true);

// ---- Start marker ----
color(start_color) {
    translate([0, 0, 0.2])
        cylinder(h=0.5, r=12, center=true, $fn=32);
    translate([0, 0, 1])
        text("START", size=5, halign="center", valign="center",
             font="Liberation Sans:style=Bold");
}

// ---- Goal marker ----
color(goal_color) {
    translate([190, 170, 0.2])
        cylinder(h=0.5, r=12, center=true, $fn=32);
    translate([190, 170, 1])
        text("GOAL", size=5, halign="center", valign="center",
             font="Liberation Sans:style=Bold");
    // Pulsing ring
    goal_pulse = 12 + 3 * sin($t * 360 * 3);
    translate([190, 170, 0.3])
        difference() {
            cylinder(h=0.3, r=goal_pulse, center=true, $fn=32);
            cylinder(h=0.5, r=goal_pulse - 1.5, center=true, $fn=32);
        }
}

// ---- Obstacles ----
// Box obstacle 1
color([0.50, 0.45, 0.35])
    translate([60, 35, 10])
        cube([20, 20, 20], center=true);
color([0.55, 0.50, 0.40])
    translate([60, 35, 20.5])
        cube([22, 22, 1], center=true);

// Cylinder obstacle 2
color([0.45, 0.40, 0.50])
    translate([160, 50, 12])
        cylinder(h=24, r=10, center=true, $fn=32);
color([0.50, 0.45, 0.55])
    translate([160, 50, 24.5])
        cylinder(h=1, r=11, center=true, $fn=32);

// Wall obstacle 3
color([0.55, 0.50, 0.45])
    translate([80, 120, 8])
        cube([60, 4, 16], center=true);

// ---- Obstacle shadows ----
color([0.22, 0.24, 0.20])
    translate([60, 35, 0.05])
        cube([22, 22, 0.1], center=true);
color([0.22, 0.24, 0.20])
    translate([160, 50, 0.05])
        cylinder(h=0.1, r=11, center=true, $fn=32);
color([0.22, 0.24, 0.20])
    translate([80, 120, 0.05])
        cube([62, 6, 0.1], center=true);

// ---- Trail (breadcrumb dots behind robot) ----
n_trail = 40;
for (i = [0 : n_trail - 1]) {
    t_i = i / n_trail;
    if (t_i < $t) {
        tp = robot_pos(t_i);
        fade = 0.3 + 0.7 * (t_i / $t);
        color([0.2, 0.7*fade, 1.0*fade, 0.6])
            translate([tp[0], tp[1], 0.2])
                cylinder(h=0.3, r=1.5, $fn=10);
    }
}

// ---- The Robot ----
translate([rx, ry, 0])
    rotate([0, 0, rhead])
        robot();

// ---- Robot shadow ----
color([0.22, 0.24, 0.20, 0.5])
    translate([rx + 2, ry - 2, 0.05])
        rotate([0, 0, rhead])
            cube([body_l + 4, body_w + 4, 0.1], center=true);

// ---- Title ----
color([0.85, 0.85, 0.85])
    translate([95, -40, 0.5])
        text("Autonomous Mobile Robot — Path Navigation", size=7,
             halign="center", font="Liberation Sans:style=Bold");

// ---- Info ----
color([0.65, 0.65, 0.65])
    translate([95, 220, 0.5])
        text("Differential drive  |  LiDAR + Camera  |  Obstacle avoidance",
             size=5, halign="center", font="Liberation Sans");

// ---- Compass rose ----
translate([260, -20, 0.5]) {
    color([0.6, 0.6, 0.6]) {
        // N-S line
        cube([0.5, 20, 0.3], center=true);
        // E-W line
        cube([20, 0.5, 0.3], center=true);
    }
    color([0.8, 0.3, 0.3])
        translate([0, 12, 0])
            text("N", size=4, halign="center", font="Liberation Sans:style=Bold");
    color([0.6, 0.6, 0.6]) {
        translate([12, 0, 0])
            text("E", size=3, halign="center", font="Liberation Sans");
        translate([0, -14, 0])
            text("S", size=3, halign="center", font="Liberation Sans");
        translate([-14, 0, 0])
            text("W", size=3, halign="center", font="Liberation Sans");
    }
    // North arrow
    color([0.8, 0.3, 0.3])
        translate([0, 11, 0.3])
            cylinder(h=0.5, r1=0, r2=2.5, $fn=3);
}

// ---- Scale bar ----
color([0.7, 0.7, 0.7]) {
    translate([30, -28, 0.3])
        cube([40, 1, 0.3], center=true);
    translate([10, -28, 0.3])
        cube([1, 4, 0.3], center=true);
    translate([50, -28, 0.3])
        cube([1, 4, 0.3], center=true);
    translate([30, -34, 0.5])
        text("40 mm", size=4, halign="center", font="Liberation Sans");
}
