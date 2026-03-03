// Assembly Line Conveyor System Simulation
// Features: component flow, sensor-triggered motion, bottleneck ID
// Animated with $t (0..1) = one full production cycle

// ---- Parameters ----
belt_len    = 300;      // total conveyor length
belt_w      = 40;       // belt width
belt_h      = 4;        // belt thickness
leg_h       = 30;       // support leg height
roller_r    = 6;        // end roller radius
n_rollers   = 12;       // intermediate rollers
station_w   = 50;       // station footprint width

// ---- Animation ----
cycle = $t * 360;       // degrees for trig
t = $t;                 // normalized 0..1

// ---- Colors ----
frame_c   = [0.35, 0.35, 0.40];
belt_c    = [0.15, 0.15, 0.18];
roller_c  = [0.55, 0.57, 0.60];
item_c1   = [0.20, 0.55, 0.85];  // blue box
item_c2   = [0.85, 0.55, 0.20];  // orange box
item_c3   = [0.25, 0.75, 0.35];  // green box
sensor_c  = [0.70, 0.10, 0.10];
active_c  = [0.10, 0.95, 0.20];  // sensor triggered
warn_c    = [1.00, 0.85, 0.00];  // bottleneck warning
reject_c  = [0.90, 0.15, 0.15];

// ---- Helper: smoothstep ----
function ss(e0, e1, x) = let(
    tt = min(1, max(0, (x-e0)/(e1-e0)))
) tt*tt*(3-2*tt);

// ---- Item positions (8 items flowing L→R) ----
// Each item: base_phase offset, speed multiplier in bottleneck zone
n_items = 8;
function item_phase(i) = i / n_items;  // staggered entry

// Item x-position: slows down in bottleneck zone (x=100..160)
function raw_x(ph) = let(p = (t + ph) % 1.0) p;  // 0..1 along belt

// Bottleneck slowdown: items compress in zone 0.33..0.53
function item_x(ph) = let(
    p = ((t + ph) % 1.0),
    // Piecewise: normal speed, then slow, then normal
    x = (p < 0.30) ? p * 1.0 :
        (p < 0.55) ? 0.30 + (p - 0.30) * 0.6 :  // 60% speed
        0.30 + 0.25 * 0.6 + (p - 0.55) * 1.1     // catch up
) x;

function item_world_x(i) = -belt_len/2 + item_x(item_phase(i)) * belt_len;

// Item visible (on belt)
function item_vis(i) = let(wx = item_world_x(i))
    (wx > -belt_len/2 + 10 && wx < belt_len/2 - 10) ? 1 : 0;

// Item in bottleneck zone
function in_bottleneck(i) = let(wx = item_world_x(i))
    (wx > 0 && wx < 60) ? 1 : 0;

// Item rejected at QC (every 4th item)
function is_rejected(i) = (i % 4 == 3) ? 1 : 0;

// Item past QC diverter
function past_qc(i) = let(wx = item_world_x(i)) (wx > 95) ? 1 : 0;

// Reject Y offset
function reject_y(i) = (is_rejected(i) && past_qc(i)) ?
    min(40, (item_world_x(i) - 95) * 1.5) : 0;

// ---- Module: support frame ----
module frame() {
    color(frame_c) {
        // Side rails
        for (s = [-1, 1])
            translate([0, s * (belt_w/2 + 3), leg_h + belt_h/2])
                cube([belt_len + 20, 4, 8], center=true);
        // Legs (6 pairs)
        for (lx = [-120, -60, 0, 60, 120]) {
            for (s = [-1, 1]) {
                translate([lx, s * (belt_w/2 + 3), leg_h/2])
                    cube([6, 6, leg_h], center=true);
                // Cross brace
                translate([lx, 0, 8])
                    cube([4, belt_w + 10, 4], center=true);
            }
        }
    }
}

// ---- Module: belt surface ----
module belt_surface() {
    // Main belt
    color(belt_c)
        translate([0, 0, leg_h + belt_h/2])
            cube([belt_len, belt_w, belt_h], center=true);
    // Belt segment lines (moving)
    seg_offset = (t % 0.1) / 0.1 * 12;
    color([0.22, 0.22, 0.25])
        for (sx = [-belt_len/2 + seg_offset : 12 : belt_len/2])
            translate([sx, 0, leg_h + belt_h + 0.2])
                cube([1.5, belt_w - 2, 0.3], center=true);
    // End rollers
    color(roller_c) {
        for (ex = [-1, 1])
            translate([ex * belt_len/2, 0, leg_h + belt_h/2])
                rotate([90, 0, 0])
                    cylinder(h=belt_w + 8, r=roller_r, center=true, $fn=24);
    }
    // Intermediate rollers (visible below belt)
    color([0.50, 0.50, 0.53])
        for (rx = [-belt_len/2 + 25 : belt_len/(n_rollers+1) : belt_len/2 - 25])
            translate([rx, 0, leg_h - 2])
                rotate([90, 0, 0])
                    cylinder(h=belt_w + 2, r=3, center=true, $fn=16);
}

// ---- Module: photoelectric sensor ----
module sensor(triggered) {
    sc = triggered ? active_c : sensor_c;
    // Emitter post
    color([0.3, 0.3, 0.35]) {
        translate([0, -belt_w/2 - 8, leg_h + belt_h + 10])
            cube([4, 4, 20], center=true);
        translate([0,  belt_w/2 + 8, leg_h + belt_h + 10])
            cube([4, 4, 20], center=true);
    }
    // Sensor heads
    color(sc) {
        translate([0, -belt_w/2 - 8, leg_h + belt_h + 18])
            sphere(r=3, $fn=16);
        translate([0,  belt_w/2 + 8, leg_h + belt_h + 18])
            sphere(r=3, $fn=16);
    }
    // Beam (when triggered)
    if (triggered) {
        color([1, 0.2, 0.2, 0.3])
            translate([0, 0, leg_h + belt_h + 18])
                rotate([90, 0, 0])
                    cylinder(h=belt_w + 12, r=0.8, center=true, $fn=8);
    }
}

// ---- Module: station marker ----
module station_label(txt, x_pos, c) {
    color(c)
        translate([x_pos, -belt_w/2 - 18, leg_h + belt_h + 25])
            text(txt, size=5, halign="center", font="Liberation Sans:style=Bold");
}

// ---- Module: status light ----
module status_light(x_pos, is_on, c) {
    translate([x_pos, -belt_w/2 - 8, leg_h + belt_h + 24]) {
        color(is_on ? c : [0.2, 0.2, 0.2])
            sphere(r=2.5, $fn=12);
        // Housing
        color([0.25, 0.25, 0.28])
            translate([0, 0, -3])
                cylinder(h=3, r=3, center=true, $fn=16);
    }
}

// ---- Module: work item (box) ----
module work_item(idx) {
    wx = item_world_x(idx);
    vis = item_vis(idx);
    ry = reject_y(idx);
    rej = is_rejected(idx);
    bn = in_bottleneck(idx);

    if (vis > 0.5) {
        c = (rej && past_qc(idx)) ? reject_c :
            (idx % 3 == 0) ? item_c1 :
            (idx % 3 == 1) ? item_c2 : item_c3;

        translate([wx, ry, leg_h + belt_h + 6]) {
            // Box body
            color(c)
                cube([12, 12, 12], center=true);
            // Label stripe
            color([1,1,1])
                translate([0, 0, 5])
                    cube([10, 10, 1.5], center=true);
            // Part number
            color([0.1,0.1,0.1])
                translate([0, 0, 6.5])
                    text(str(idx+1), size=4, halign="center", valign="center");
            // Bottleneck: warning halo
            if (bn > 0.5 && !rej) {
                color([1, 0.85, 0, 0.25])
                    cube([16, 16, 14], center=true);
            }
        }
    }
}

// ---- Module: Station 1 - Loading ----
module station_loading() {
    x = -110;
    // Chute
    color([0.5, 0.5, 0.55]) {
        translate([x, 0, leg_h + belt_h + 25])
            rotate([0, 15, 0])
                cube([8, 30, 30], center=true);
        // Hopper
        translate([x - 12, 0, leg_h + belt_h + 40])
            cube([20, 34, 12], center=true);
    }
    // Items in hopper
    for (hi = [0:2])
        color(item_c1)
            translate([x - 12, 0, leg_h + belt_h + 48 + hi * 14])
                cube([11, 11, 11], center=true);
}

// ---- Module: Station 2 - Bottleneck (slow process) ----
module station_bottleneck() {
    x = 30;
    // Machine housing
    color([0.45, 0.30, 0.15]) {
        translate([x, 0, leg_h + belt_h + 28])
            cube([55, 50, 24], center=true);
    }
    // Machine top with warning light
    color([0.50, 0.35, 0.18])
        translate([x, 0, leg_h + belt_h + 41])
            cube([50, 46, 2], center=true);

    // Spinning tool (animated)
    translate([x, 0, leg_h + belt_h + 43]) {
        color([0.6, 0.6, 0.65])
            rotate([0, 0, cycle * 3])
                for (a = [0, 90, 180, 270])
                    rotate([0, 0, a])
                        translate([8, 0, 0])
                            cube([12, 3, 3], center=true);
        color(roller_c)
            cylinder(h=5, r=4, center=true, $fn=20);
    }

    // Queue indicator bars
    // Count items in bottleneck zone
    queue_intensity = ss(0.2, 0.5, t) * (1 - ss(0.7, 0.9, t));
    // Warning beacon
    blink = (sin(cycle * 4) > 0) ? 1 : 0;
    status_light(x, blink > 0.5, warn_c);

    // "BOTTLENECK" label
    color(warn_c)
        translate([x, belt_w/2 + 15, leg_h + belt_h + 20])
            text("SLOW", size=5, halign="center",
                 font="Liberation Sans:style=Bold");

    // Queue length bar
    q_len = queue_intensity * 40;
    color([1, 0.3, 0.1])
        translate([x - 25, belt_w/2 + 15, leg_h + belt_h + 12])
            cube([q_len, 3, 3], center=true);
    color([0.8, 0.8, 0.8])
        translate([x - 25, belt_w/2 + 15, leg_h + belt_h + 8])
            text("Queue", size=3, halign="center");
}

// ---- Module: Station 3 - QC / Diverter ----
module station_qc() {
    x = 95;
    // Scanner arch
    color([0.3, 0.3, 0.6]) {
        translate([x, -belt_w/2 - 2, leg_h + belt_h])
            cube([6, 4, 28]);
        translate([x,  belt_w/2 - 2, leg_h + belt_h])
            cube([6, 4, 28]);
        translate([x, 0, leg_h + belt_h + 28])
            cube([6, belt_w + 8, 4], center=true);
    }
    // Scanning beam (sweeping)
    scan_y = sin(cycle * 6) * belt_w/2;
    color([0.2, 0.8, 0.2, 0.4])
        translate([x + 3, scan_y, leg_h + belt_h + 14])
            cube([1, 3, 24], center=true);

    // Diverter arm (pushes rejects off belt)
    // Check if a rejected item is near
    any_reject_near = 0;  // simplified
    diverter_angle = 15 * sin(cycle * 2);
    color([0.6, 0.2, 0.2])
        translate([x + 20, -belt_w/2 - 3, leg_h + belt_h + 6])
            rotate([0, 0, diverter_angle])
                cube([4, 25, 8], center=true);

    // Reject bin
    color([0.5, 0.15, 0.15]) {
        translate([x + 25, 45, leg_h/2]) {
            difference() {
                cube([30, 24, leg_h], center=true);
                translate([0, 0, 3])
                    cube([26, 20, leg_h], center=true);
            }
        }
    }
    color([1,1,1])
        translate([x + 25, 45, leg_h + 2])
            text("REJECT", size=3, halign="center",
                 font="Liberation Sans:style=Bold");

    // QC pass/fail lights
    qc_pass = (sin(cycle * 3) > 0) ? 1 : 0;
    status_light(x - 5, qc_pass > 0.5, active_c);
    status_light(x + 5, qc_pass < 0.5, reject_c);
}

// ---- Module: output station ----
module station_output() {
    x = 135;
    // Collection bin
    color([0.3, 0.55, 0.3]) {
        translate([x, 0, leg_h/2]) {
            difference() {
                cube([30, 36, leg_h], center=true);
                translate([0, 0, 3])
                    cube([26, 32, leg_h], center=true);
            }
        }
    }
    // Finished items in bin
    for (bi = [0:2])
        color(item_c3)
            translate([x - 4 + bi*5, -4 + bi*3, 10 + bi*6])
                cube([10, 10, 10], center=true);

    color([1,1,1])
        translate([x, 0, leg_h + 4])
            text("OUTPUT", size=3.5, halign="center",
                 font="Liberation Sans:style=Bold");
}

// ---- Module: throughput display ----
module throughput_display() {
    // Digital display board
    translate([0, -belt_w/2 - 35, leg_h + 40]) {
        // Board
        color([0.1, 0.1, 0.15])
            cube([120, 2, 35], center=true);
        // Title
        color([0.0, 0.9, 1.0])
            translate([0, -1.5, 12])
                text("PRODUCTION MONITOR", size=4, halign="center",
                     font="Liberation Sans:style=Bold");
        // Throughput
        rate = 80 + 15 * sin(cycle);
        color([0.2, 1.0, 0.3])
            translate([-45, -1.5, 2])
                text(str("Rate: ", floor(rate), " pcs/hr"), size=3.5,
                     font="Liberation Mono:style=Bold");
        // Bottleneck status
        bn_pct = 35 + 20 * sin(cycle * 0.7);
        color(warn_c)
            translate([-45, -1.5, -7])
                text(str("Bottleneck: ", floor(bn_pct), "% util"), size=3.5,
                     font="Liberation Mono:style=Bold");
        // Efficiency bar
        eff = 0.65 + 0.15 * sin(cycle * 0.5);
        color([0.3, 0.3, 0.35])
            translate([30, -1.5, -7])
                cube([40, 1, 5], center=true);
        color(eff > 0.7 ? active_c : warn_c)
            translate([30 - 20 + eff*20, -2, -7])
                cube([eff * 40, 1.5, 5], center=true);
    }
}

// ---- Module: floor ----
module floor_grid() {
    // Ground plane
    color([0.25, 0.25, 0.28])
        translate([0, 0, -1])
            cube([380, 140, 2], center=true);
    // Grid lines
    color([0.30, 0.30, 0.33])
        for (gx = [-180 : 30 : 180])
            translate([gx, 0, 0.1])
                cube([0.5, 140, 0.2], center=true);
    color([0.30, 0.30, 0.33])
        for (gy = [-60 : 30 : 60])
            translate([0, gy, 0.1])
                cube([380, 0.5, 0.2], center=true);
    // Safety zone markings (yellow stripes)
    color([0.9, 0.8, 0.1])
        for (sx = [-140, -100, -60, -20, 20, 60, 100, 140])
            translate([sx, -belt_w/2 - 22, 0.2])
                cube([8, 2, 0.3], center=true);
}

// ---- Module: title ----
module title() {
    color([1,1,1])
        translate([0, belt_w/2 + 50, leg_h + 45])
            text("Assembly Line Conveyor Simulation",
                 size=6, halign="center",
                 font="Liberation Sans:style=Bold");
    color([0.7, 0.7, 0.75])
        translate([0, belt_w/2 + 50, leg_h + 37])
            text("Component Flow  |  Sensor-Triggered Motion  |  Bottleneck Detection",
                 size=3, halign="center");
}

// ---- Module: flow arrows ----
module flow_arrows() {
    color([0.1, 0.7, 0.2, 0.5])
        for (ax = [-130, -80, -30, 70, 120])
            translate([ax, 0, leg_h + belt_h + 1])
                rotate([0, 0, 0]) {
                    // Arrow shaft
                    cube([10, 2, 0.5], center=true);
                    // Arrow head
                    translate([6, 0, 0])
                        rotate([0, 0, -90])
                            cylinder(h=0.5, r=3, $fn=3, center=true);
                }
}

// ========== ASSEMBLY ==========

// Sensors at key positions
// Sensor 1: loading zone
s1_trig = (sin(cycle * 4) > 0.3) ? 1 : 0;
// Sensor 2: pre-bottleneck
s2_trig = (sin(cycle * 3 + 60) > 0.2) ? 1 : 0;
// Sensor 3: post-bottleneck
s3_trig = (sin(cycle * 2.5 + 120) > 0.4) ? 1 : 0;
// Sensor 4: QC station
s4_trig = (sin(cycle * 3.5 + 180) > 0.3) ? 1 : 0;

// Build scene
frame();
belt_surface();
flow_arrows();
floor_grid();
title();
throughput_display();

// Sensors
translate([-80, 0, 0])  sensor(s1_trig);
translate([-10, 0, 0])  sensor(s2_trig);
translate([60, 0, 0])   sensor(s3_trig);
translate([95, 0, 0])   sensor(s4_trig);

// Sensor labels
color([0.8,0.8,0.8]) {
    translate([-80, belt_w/2 + 15, leg_h + belt_h + 22])
        text("S1", size=4, halign="center");
    translate([-10, belt_w/2 + 15, leg_h + belt_h + 22])
        text("S2", size=4, halign="center");
    translate([60, belt_w/2 + 15, leg_h + belt_h + 22])
        text("S3", size=4, halign="center");
    translate([95, belt_w/2 + 15, leg_h + belt_h + 22])
        text("S4", size=4, halign="center");
}

// Stations
station_loading();
station_bottleneck();
station_qc();
station_output();

// Station labels
station_label("LOAD", -110, [0.8, 0.8, 0.8]);
station_label("PROCESS", 30, warn_c);
station_label("QC CHECK", 95, [0.3, 0.3, 0.7]);
station_label("DONE", 135, [0.3, 0.7, 0.3]);

// Work items
for (i = [0 : n_items - 1])
    work_item(i);

// === End of Assembly Line Simulation ===
