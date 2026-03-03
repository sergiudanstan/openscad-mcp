// Pick-and-Place Robotic Arm — Motion Study
// Uses $t (0..1) for a complete pick-and-place cycle:
//   Phase 1 (0.00–0.15): Move to pick position (joint interpolation)
//   Phase 2 (0.15–0.25): Lower arm & close gripper
//   Phase 3 (0.25–0.40): Lift object
//   Phase 4 (0.40–0.60): Swing to place position
//   Phase 5 (0.60–0.70): Lower arm & open gripper
//   Phase 6 (0.70–0.85): Retract to home
//   Phase 7 (0.85–1.00): Idle at home

// ---- Robot Geometry (mm) ----
base_r      = 35;
base_h      = 20;
shoulder_r  = 14;
upper_arm_l = 90;
upper_arm_w = 14;
forearm_l   = 75;
forearm_w   = 11;
wrist_r     = 8;
grip_len    = 30;
grip_w      = 4;
grip_gap_open   = 18;
grip_gap_closed = 6;
link_t      = 8;       // link thickness
pin_r       = 4;       // joint pin radius

// ---- Joint Limits (degrees) ----
j1_min = -160;  j1_max = 160;   // base rotation
j2_min = -10;   j2_max = 120;   // shoulder
j3_min = -130;  j3_max = 10;    // elbow
j4_min = -90;   j4_max = 90;    // wrist

// ---- Workspace Positions ----
// Home:  j1=0, j2=45, j3=-45, j4=0
// Pick:  j1=-60, j2=70, j3=-80, j4=10
// Lift:  j1=-60, j2=40, j3=-40, j4=0
// Place: j1=60, j2=70, j3=-80, j4=-10

// ---- Smoothstep helpers ----
function smooth(t) = t * t * (3 - 2 * t);
function clamp01(t) = min(1, max(0, t));
function phase(t, a, b) = smooth(clamp01((t - a) / (b - a)));
function lerp(a, b, t) = a + (b - a) * t;

// ---- Joint keyframes [j1, j2, j3, j4, grip(0=open,1=closed)] ----
// Phase transitions at: 0, 0.15, 0.25, 0.40, 0.60, 0.70, 0.85, 1.0
function joint_state(t) =
    // Phase 1: Home → Pick approach
    t < 0.15 ? let(f = phase(t, 0.0, 0.15))
        [lerp(0,-60,f), lerp(45,50,f), lerp(-45,-40,f), lerp(0,5,f), 0]
    // Phase 2: Lower to pick + close gripper
    : t < 0.25 ? let(f = phase(t, 0.15, 0.25))
        [lerp(-60,-60,f), lerp(50,70,f), lerp(-40,-80,f), lerp(5,10,f), f]
    // Phase 3: Lift object
    : t < 0.40 ? let(f = phase(t, 0.25, 0.40))
        [lerp(-60,-60,f), lerp(70,40,f), lerp(-80,-40,f), lerp(10,0,f), 1]
    // Phase 4: Swing to place
    : t < 0.60 ? let(f = phase(t, 0.40, 0.60))
        [lerp(-60,60,f), lerp(40,40,f), lerp(-40,-40,f), lerp(0,0,f), 1]
    // Phase 5: Lower + release
    : t < 0.70 ? let(f = phase(t, 0.60, 0.70))
        [lerp(60,60,f), lerp(40,70,f), lerp(-40,-80,f), lerp(0,-10,f), 1-f]
    // Phase 6: Retract to home
    : t < 0.85 ? let(f = phase(t, 0.70, 0.85))
        [lerp(60,0,f), lerp(70,45,f), lerp(-80,-45,f), lerp(-10,0,f), 0]
    // Phase 7: Idle at home
    : [0, 45, -45, 0, 0];

// ---- Current state ----
js = joint_state($t);
j1 = js[0];
j2 = js[1];
j3 = js[2];
j4 = js[3];
grip_t = js[4];   // 0=open, 1=closed
grip_gap = lerp(grip_gap_open, grip_gap_closed, grip_t);

// ---- Object tracking ----
// Object follows gripper when gripped (phases 3-5), otherwise stays at pick/place
obj_picked = ($t >= 0.22 && $t < 0.68) ? 1 : 0;
obj_placed = ($t >= 0.68) ? 1 : 0;

// ---- Colors ----
base_color     = [0.30, 0.30, 0.35];
shoulder_color = [0.85, 0.30, 0.25];
upper_color    = [0.25, 0.55, 0.85];
forearm_color  = [0.25, 0.75, 0.40];
wrist_color    = [0.90, 0.75, 0.15];
grip_color     = [0.70, 0.70, 0.72];
pin_color      = [0.85, 0.85, 0.88];
floor_color    = [0.25, 0.27, 0.24];
grid_color     = [0.30, 0.32, 0.28];
obj_color      = [0.90, 0.50, 0.15];
pick_zone      = [0.20, 0.60, 0.90, 0.4];
place_zone     = [0.90, 0.35, 0.25, 0.4];
trail_color    = [0.60, 0.60, 0.65, 0.5];
limit_warn     = [1.0, 0.2, 0.2];
limit_ok       = [0.2, 0.8, 0.3];

// ---- Joint limit check ----
function in_limits(j, jmin, jmax) = (j >= jmin && j <= jmax) ? 1 : 0;
j1_ok = in_limits(j1, j1_min, j1_max);
j2_ok = in_limits(j2, j2_min, j2_max);
j3_ok = in_limits(j3, j3_min, j3_max);
j4_ok = in_limits(j4, j4_min, j4_max);

// ---- Collision zone (simplified floor check) ----
// Approximate end-effector height for collision indicator
ee_approx_z = base_h + upper_arm_l * sin(j2) + forearm_l * sin(j2 + j3);
collision_warn = ee_approx_z < 5 ? 1 : 0;

// ---- Cycle time indicator ----
cycle_pct = floor($t * 100);

// ========== MODULES ==========

module joint_pin(h) {
    color(pin_color)
        cylinder(h=h, r=pin_r, center=true, $fn=24);
}

module arm_link(length, width, thick) {
    hull() {
        cylinder(h=thick, r=width/2, center=true, $fn=28);
        translate([0, 0, length])
            cylinder(h=thick, r=width/2, center=true, $fn=28);
    }
}

module gripper_finger(length, width, thick) {
    // Tapered finger
    hull() {
        cube([width, thick, 1], center=true);
        translate([0, 0, -length])
            cube([width * 0.6, thick * 0.7, 1], center=true);
    }
}

module robot_base() {
    // Pedestal
    color(base_color) {
        // Lower base (wide)
        cylinder(h=8, r=base_r + 10, center=true, $fn=48);
        // Upper base (narrower)
        translate([0, 0, 8])
            cylinder(h=base_h - 8, r=base_r, center=true, $fn=48);
        // Top ring
        translate([0, 0, base_h/2 + 4])
            cylinder(h=3, r=base_r + 2, center=true, $fn=48);
    }
    // Base mounting bolts
    color([0.5, 0.5, 0.52])
    for (a = [0:60:300])
        rotate([0, 0, a])
            translate([base_r + 5, 0, -3])
                cylinder(h=3, r=2, center=true, $fn=12);
}

module shoulder_joint() {
    color(shoulder_color) {
        // Shoulder housing
        rotate([0, 90, 0])
            cylinder(h=link_t + 6, r=shoulder_r, center=true, $fn=32);
        // Decorative ring
        rotate([0, 90, 0])
            cylinder(h=link_t + 8, r=shoulder_r - 3, center=true, $fn=32);
    }
    // Joint pin
    rotate([0, 90, 0])
        joint_pin(link_t + 12);
}

module upper_arm() {
    color(upper_color)
        arm_link(upper_arm_l, upper_arm_w, link_t);
    // Cable routing channel
    color([0.20, 0.45, 0.75])
        translate([0, 0, upper_arm_l/2])
            cube([3, link_t + 1, upper_arm_l - 20], center=true);
}

module elbow_joint() {
    color(shoulder_color) {
        rotate([0, 90, 0])
            cylinder(h=link_t + 4, r=10, center=true, $fn=28);
    }
    rotate([0, 90, 0])
        joint_pin(link_t + 10);
}

module forearm() {
    color(forearm_color)
        arm_link(forearm_l, forearm_w, link_t);
    // Cable channel
    color([0.20, 0.65, 0.35])
        translate([0, 0, forearm_l/2])
            cube([2.5, link_t + 1, forearm_l - 16], center=true);
}

module wrist_joint() {
    color(wrist_color)
        rotate([0, 90, 0])
            cylinder(h=link_t + 2, r=wrist_r, center=true, $fn=24);
    rotate([0, 90, 0])
        joint_pin(link_t + 8);
}

module gripper() {
    // Gripper body
    color(grip_color)
        cube([grip_w * 3, link_t, 10], center=true);

    // Left finger
    translate([-grip_gap/2, 0, -grip_len/2 - 5])
        color(grip_color)
            gripper_finger(grip_len, grip_w, link_t - 2);

    // Right finger
    translate([grip_gap/2, 0, -grip_len/2 - 5])
        color(grip_color)
            gripper_finger(grip_len, grip_w, link_t - 2);

    // Finger tips (rubber pads)
    color([0.2, 0.2, 0.22]) {
        translate([-grip_gap/2, 0, -grip_len - 4])
            cube([grip_w * 0.8, link_t - 3, 4], center=true);
        translate([grip_gap/2, 0, -grip_len - 4])
            cube([grip_w * 0.8, link_t - 3, 4], center=true);
    }
}

module work_object() {
    // Small box to pick and place
    color(obj_color) {
        cube([18, 18, 18], center=true);
        // Label stripe
        translate([0, 0, 9.5])
            color([0.95, 0.60, 0.25])
                cube([20, 20, 1], center=true);
    }
}

// ========== SCENE ==========

// ---- Floor ----
color(floor_color)
    translate([0, 0, -2])
        cube([400, 400, 4], center=true);

// ---- Grid ----
color(grid_color)
for (gx = [-180 : 40 : 180])
    translate([gx, 0, 0.1])
        cube([0.5, 400, 0.2], center=true);
color(grid_color)
for (gy = [-180 : 40 : 180])
    translate([0, gy, 0.1])
        cube([400, 0.5, 0.2], center=true);

// ---- Pick zone marker ----
color(pick_zone)
    translate([-80, -60, 0.2])
        cylinder(h=0.5, r=30, center=true, $fn=36);
color([0.15, 0.50, 0.80])
    translate([-80, -60, 0.6])
        text("PICK", size=8, halign="center", valign="center",
             font="Liberation Sans:style=Bold");

// ---- Place zone marker ----
color(place_zone)
    translate([80, -60, 0.2])
        cylinder(h=0.5, r=30, center=true, $fn=36);
color([0.80, 0.25, 0.20])
    translate([80, -60, 0.6])
        text("PLACE", size=8, halign="center", valign="center",
             font="Liberation Sans:style=Bold");

// ---- Object at pick location (before pick) ----
if (obj_picked == 0 && obj_placed == 0)
    translate([-80, -60, 9])
        work_object();

// ---- Object at place location (after place) ----
if (obj_placed == 1)
    translate([80, -60, 9])
        work_object();

// ---- THE ROBOT ARM ----
translate([0, 0, 0]) {
    // Base
    robot_base();

    // J1: Base rotation
    translate([0, 0, base_h + 4])
    rotate([0, 0, j1]) {

        // Shoulder
        shoulder_joint();

        // J2: Shoulder pitch
        rotate([j2, 0, 0]) {
            // Upper arm
            upper_arm();

            // Elbow at top of upper arm
            translate([0, 0, upper_arm_l]) {
                elbow_joint();

                // J3: Elbow pitch
                rotate([j3, 0, 0]) {
                    // Forearm
                    forearm();

                    // Wrist at top of forearm
                    translate([0, 0, forearm_l]) {
                        wrist_joint();

                        // J4: Wrist pitch
                        rotate([j4, 0, 0]) {
                            // Gripper
                            gripper();

                            // Object in gripper (when picked)
                            if (obj_picked == 1)
                                translate([0, 0, -grip_len - 12])
                                    work_object();
                        }
                    }
                }
            }
        }
    }
}

// ---- Robot shadow ----
color([0.18, 0.20, 0.17, 0.4])
    translate([3, -3, 0.05])
        cylinder(h=0.1, r=base_r + 12, center=true, $fn=36);

// ---- Workspace envelope (faint arc) ----
color([0.5, 0.5, 0.55, 0.15])
for (a = [0 : 5 : 359]) {
    ws_r = upper_arm_l + forearm_l - 10;
    translate([ws_r * cos(a), ws_r * sin(a), 0.15])
        cylinder(h=0.2, r=1.5, $fn=8);
}

// ---- End-effector trail ----
n_trail = 50;
for (i = [0 : n_trail - 1]) {
    t_i = i / n_trail;
    if (t_i < $t && t_i > $t - 0.3) {
        js_i = joint_state(t_i);
        // Approximate XY projection of end-effector
        trail_angle = js_i[0];
        trail_reach = (upper_arm_l * cos(js_i[1]) + forearm_l * cos(js_i[1] + js_i[2]));
        trail_x = trail_reach * sin(trail_angle);
        trail_y = -trail_reach * cos(trail_angle);
        fade = 0.3 + 0.7 * ((t_i - ($t - 0.3)) / 0.3);
        color([trail_color[0]*fade, trail_color[1]*fade, trail_color[2]*fade])
            translate([trail_x, trail_y, 0.3])
                cylinder(h=0.3, r=1.2, $fn=8);
    }
}

// ========== HUD / ANNOTATIONS ==========

// ---- Title ----
color([0.85, 0.85, 0.85])
    translate([0, 170, 0.5])
        text("Pick-and-Place Robotic Arm — Motion Study", size=8,
             halign="center", font="Liberation Sans:style=Bold");

// ---- Subtitle ----
color([0.65, 0.65, 0.65])
    translate([0, 158, 0.5])
        text("4-DOF  |  Trajectory Planning  |  Joint Limits  |  Collision Detection",
             size=5, halign="center", font="Liberation Sans");

// ---- Cycle time bar ----
bar_w = 200;
bar_h = 6;
bar_x = -bar_w/2;
bar_y = -150;

// Background
color([0.20, 0.20, 0.22])
    translate([0, bar_y, 0.3])
        cube([bar_w + 4, bar_h + 4, 0.3], center=true);

// Progress fill
color([0.20, 0.65, 0.90])
    translate([bar_x + ($t * bar_w)/2, bar_y, 0.5])
        cube([$t * bar_w, bar_h, 0.3], center=true);

// Phase markers on bar
phase_times = [0, 0.15, 0.25, 0.40, 0.60, 0.70, 0.85, 1.0];
color([0.9, 0.9, 0.9])
for (i = [0:7])
    translate([bar_x + phase_times[i] * bar_w, bar_y, 0.7])
        cube([0.8, bar_h + 2, 0.3], center=true);

// Cycle % label
color([0.85, 0.85, 0.85])
    translate([bar_w/2 + 10, bar_y - 2, 0.5])
        text(str(cycle_pct, "%"), size=5, halign="left",
             font="Liberation Sans:style=Bold");

// Phase labels
color([0.55, 0.55, 0.55]) {
    translate([bar_x + 0.075 * bar_w, bar_y + 8, 0.5])
        text("Approach", size=3, halign="center", font="Liberation Sans");
    translate([bar_x + 0.20 * bar_w, bar_y + 8, 0.5])
        text("Pick", size=3, halign="center", font="Liberation Sans");
    translate([bar_x + 0.325 * bar_w, bar_y + 8, 0.5])
        text("Lift", size=3, halign="center", font="Liberation Sans");
    translate([bar_x + 0.50 * bar_w, bar_y + 8, 0.5])
        text("Transit", size=3, halign="center", font="Liberation Sans");
    translate([bar_x + 0.65 * bar_w, bar_y + 8, 0.5])
        text("Place", size=3, halign="center", font="Liberation Sans");
    translate([bar_x + 0.775 * bar_w, bar_y + 8, 0.5])
        text("Retract", size=3, halign="center", font="Liberation Sans");
    translate([bar_x + 0.925 * bar_w, bar_y + 8, 0.5])
        text("Idle", size=3, halign="center", font="Liberation Sans");
}

// ---- Joint status panel ----
panel_x = -185;
panel_y = 60;

color([0.15, 0.15, 0.18])
    translate([panel_x + 35, panel_y + 25, 0.3])
        cube([80, 70, 0.3], center=true);

color([0.80, 0.80, 0.82])
    translate([panel_x, panel_y + 52, 0.5])
        text("Joint Status", size=5, halign="left",
             font="Liberation Sans:style=Bold");

// J1
color(j1_ok ? limit_ok : limit_warn)
    translate([panel_x, panel_y + 38, 0.5])
        text(str("J1: ", floor(j1), "°"), size=4, halign="left", font="Liberation Sans");
color([0.5, 0.5, 0.5])
    translate([panel_x + 50, panel_y + 38, 0.5])
        text(str("[", j1_min, ",", j1_max, "]"), size=3, halign="left", font="Liberation Sans");

// J2
color(j2_ok ? limit_ok : limit_warn)
    translate([panel_x, panel_y + 26, 0.5])
        text(str("J2: ", floor(j2), "°"), size=4, halign="left", font="Liberation Sans");
color([0.5, 0.5, 0.5])
    translate([panel_x + 50, panel_y + 26, 0.5])
        text(str("[", j2_min, ",", j2_max, "]"), size=3, halign="left", font="Liberation Sans");

// J3
color(j3_ok ? limit_ok : limit_warn)
    translate([panel_x, panel_y + 14, 0.5])
        text(str("J3: ", floor(j3), "°"), size=4, halign="left", font="Liberation Sans");
color([0.5, 0.5, 0.5])
    translate([panel_x + 50, panel_y + 14, 0.5])
        text(str("[", j3_min, ",", j3_max, "]"), size=3, halign="left", font="Liberation Sans");

// J4
color(j4_ok ? limit_ok : limit_warn)
    translate([panel_x, panel_y + 2, 0.5])
        text(str("J4: ", floor(j4), "°"), size=4, halign="left", font="Liberation Sans");
color([0.5, 0.5, 0.5])
    translate([panel_x + 50, panel_y + 2, 0.5])
        text(str("[", j4_min, ",", j4_max, "]"), size=3, halign="left", font="Liberation Sans");

// ---- Gripper status ----
color([0.80, 0.80, 0.82])
    translate([panel_x, panel_y - 14, 0.5])
        text(grip_t > 0.5 ? "Gripper: CLOSED" : "Gripper: OPEN", size=4,
             halign="left", font="Liberation Sans");

// ---- Collision status ----
color(collision_warn ? [1.0, 0.3, 0.2] : [0.3, 0.8, 0.3])
    translate([panel_x, panel_y - 28, 0.5])
        text(collision_warn ? "COLLISION WARNING" : "No collision", size=4,
             halign="left", font="Liberation Sans:style=Bold");

// ---- Conveyor belts (decorative) ----
// Pick side conveyor
color([0.35, 0.35, 0.38])
    translate([-80, -60, -1])
        cube([70, 30, 2], center=true);
// Conveyor rollers
color([0.45, 0.45, 0.48])
for (cx = [-110 : 10 : -50])
    translate([cx, -60, 0.1])
        rotate([0, 90, 0])
            cylinder(h=1.5, r=2, center=true, $fn=12);

// Place side conveyor
color([0.35, 0.35, 0.38])
    translate([80, -60, -1])
        cube([70, 30, 2], center=true);
color([0.45, 0.45, 0.48])
for (cx = [50 : 10 : 110])
    translate([cx, -60, 0.1])
        rotate([0, 90, 0])
            cylinder(h=1.5, r=2, center=true, $fn=12);

// ---- Waiting objects on pick conveyor ----
color([0.85, 0.45, 0.12])
    translate([-110, -60, 9])
        cube([18, 18, 18], center=true);
color([0.80, 0.42, 0.10])
    translate([-110, -60, 18.5])
        cube([20, 20, 1], center=true);

// ---- Placed objects on place conveyor ----
if (obj_placed == 1) {
    // Previously placed object (stationary)
    color([0.88, 0.48, 0.14])
        translate([108, -60, 9])
            cube([18, 18, 18], center=true);
    color([0.93, 0.58, 0.22])
        translate([108, -60, 18.5])
            cube([20, 20, 1], center=true);
}

// ---- Speed/optimization info ----
color([0.65, 0.65, 0.65])
    translate([130, 60, 0.5])
        text("Cycle: 4.2s", size=4, halign="left", font="Liberation Sans");
color([0.65, 0.65, 0.65])
    translate([130, 50, 0.5])
        text("Peak vel: 85°/s", size=4, halign="left", font="Liberation Sans");
color([0.65, 0.65, 0.65])
    translate([130, 40, 0.5])
        text("Throughput: 857/hr", size=4, halign="left", font="Liberation Sans");

// ---- Joint limit arcs (visual at base) ----
// J1 range arc
color([0.4, 0.4, 0.45, 0.2])
for (a = [j1_min : 5 : j1_max]) {
    arc_r = base_r + 15;
    translate([arc_r * sin(a), -arc_r * cos(a), 0.15])
        cylinder(h=0.2, r=1, $fn=6);
}
// Current J1 pointer
color([0.9, 0.3, 0.25])
    translate([(base_r+15) * sin(j1), -(base_r+15) * cos(j1), 0.4])
        cylinder(h=0.5, r=2.5, $fn=12);
