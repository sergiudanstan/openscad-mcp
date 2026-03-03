// Bezier Linkages — Curved Four-Bar Mechanism
// Links shaped as cubic Bezier curves instead of straight bars
// Coupler point traces a closed curve; Bezier control polygons shown
// Animated with $t (0..1) for one full crank revolution
//
// Demonstrates:
//   1. Cubic Bezier interpolation for link geometry
//   2. Four-bar linkage kinematics (circle-circle intersection)
//   3. Coupler-curve tracing
//   4. Control-polygon visualization

// ======== Linkage Dimensions (mm) ========
a0 = 60;        // ground link (fixed pivot distance)
a1 = 22;        // crank length
a2 = 65;        // coupler length
a3 = 45;        // rocker length

// Coupler trace point
cp_frac = 0.45;    // fraction along coupler line A→B
cp_perp = 22;      // perpendicular offset (forms coupler triangle)

// Link / joint sizing
thick    = 5;       // link thickness (z)
curve_r  = 3.5;     // Bezier link cross-section radius
pin_r    = 2.5;     // joint pin radius
pin_h    = thick * 2.8;

// Resolution
n_seg   = 30;       // segments per Bezier link
n_trace = 80;       // coupler trace dots
n_ctrl  = 20;       // Bezier overlay curve segments

// Base plate
base_w = 160;
base_d = 130;
base_t = 3;

// ======== Colors ========
col_crank   = [0.90, 0.22, 0.22];   // red
col_coupler = [0.20, 0.50, 0.90];   // blue
col_rocker  = [0.18, 0.75, 0.30];   // green
col_frame   = [0.32, 0.32, 0.38];   // dark gray
col_pin     = [0.88, 0.88, 0.88];   // silver
col_trace   = [1.00, 0.58, 0.05];   // orange
col_ctrl    = [0.65, 0.18, 0.72];   // purple
col_ghost   = [0.50, 0.50, 0.55];   // ghost outline
col_ext     = [0.15, 0.40, 0.80];   // extension arm

// ======== Z-layer offsets ========
z_base    = -thick/2 - base_t - 3;
z_crank   =  thick * 0.7;
z_coupler =  0;
z_rocker  = -thick * 0.7;
z_ctrl    =  thick + 3;

// ======== Kinematics: Four-Bar Solver ========
theta1 = $t * 360;               // crank angle (deg)

// Crank pin A
Ax = a1 * cos(theta1);
Ay = a1 * sin(theta1);

// Circle-circle intersection → rocker pin B
//   Circle 1: center A, radius a2
//   Circle 2: center O3=(a0,0), radius a3
dx_AB = a0 - Ax;
dy_AB = -Ay;
d_AB  = sqrt(dx_AB*dx_AB + dy_AB*dy_AB);
s_AB  = (d_AB*d_AB + a2*a2 - a3*a3) / (2 * d_AB);
h_AB  = sqrt(max(0, a2*a2 - s_AB*s_AB));

ux = dx_AB / d_AB;
uy = dy_AB / d_AB;

// Choose the "open" configuration (B generally above baseline)
Bx = Ax + s_AB * ux - h_AB * uy;
By = Ay + s_AB * uy + h_AB * ux;

// Coupler angle
theta2 = atan2(By - Ay, Bx - Ax);

// Coupler trace point C  (forms a triangle with A and B)
Cx = Ax + cp_frac * (Bx - Ax) - cp_perp * sin(theta2);
Cy = Ay + cp_frac * (By - Ay) + cp_perp * cos(theta2);

// ======== Bezier Math ========
function bez3(P0, P1, P2, P3, t) =
    (1-t)*(1-t)*(1-t) * P0 +
    3*(1-t)*(1-t)*t   * P1 +
    3*(1-t)*t*t        * P2 +
    t*t*t              * P3;

// Generate control points for a curved link from p0→p1
//   bulge  = lateral offset of control points (sign = side)
//   skew   = longitudinal shift (0.33 = symmetric, vary for S-curves)
function make_ctrl(p0, p1, bulge, skew=0.33) =
    let(
        ddx = p1[0] - p0[0],
        ddy = p1[1] - p0[1],
        len = sqrt(ddx*ddx + ddy*ddy),
        nx  = -ddy / max(len, 0.001),
        ny  =  ddx / max(len, 0.001)
    ) [
        p0,
        [p0[0] + ddx*skew       + nx*bulge,
         p0[1] + ddy*skew       + ny*bulge],
        [p0[0] + ddx*(1-skew)   - nx*bulge*0.4,
         p0[1] + ddy*(1-skew)   - ny*bulge*0.4],
        p1
    ];

// ======== Modules ========

// --- Curved link (Bezier-shaped bar) ---
module bezier_link(p0, p1, bulge, radius, col, z_off=0, skew=0.33) {
    pts = make_ctrl(p0, p1, bulge, skew);
    translate([0, 0, z_off])
        color(col)
            for (i = [0 : n_seg - 1]) {
                t0 = i / n_seg;
                t1 = (i + 1) / n_seg;
                pt0 = bez3(pts[0], pts[1], pts[2], pts[3], t0);
                pt1 = bez3(pts[0], pts[1], pts[2], pts[3], t1);
                hull() {
                    translate([pt0[0], pt0[1], 0])
                        cylinder(h=thick, r=radius, center=true, $fn=16);
                    translate([pt1[0], pt1[1], 0])
                        cylinder(h=thick, r=radius, center=true, $fn=16);
                }
            }
}

// --- Control polygon visualization ---
module ctrl_polygon(p0, p1, bulge, z_off, skew=0.33) {
    pts = make_ctrl(p0, p1, bulge, skew);
    translate([0, 0, z_off]) {
        // Control points (purple spheres)
        for (i = [0 : 3])
            translate([pts[i][0], pts[i][1], 0])
                color(col_ctrl)
                    sphere(r=1.8, $fn=14);

        // Control polygon edges (thin bars)
        for (i = [0 : 2]) {
            cx = (pts[i][0] + pts[i+1][0]) / 2;
            cy = (pts[i][1] + pts[i+1][1]) / 2;
            ex = pts[i+1][0] - pts[i][0];
            ey = pts[i+1][1] - pts[i][1];
            elen = sqrt(ex*ex + ey*ey);
            eang = atan2(ey, ex);
            color(col_ctrl, 0.45)
                translate([cx, cy, 0])
                    rotate([0, 0, eang])
                        cube([elen, 0.6, 0.6], center=true);
        }
    }
}

// --- Pin joint ---
module pin_joint(x, y) {
    translate([x, y, 0])
        color(col_pin)
            cylinder(h=pin_h, r=pin_r, center=true, $fn=20);
}

// --- Fixed bearing (ring around ground pivot) ---
module bearing(x, y) {
    translate([x, y, 0])
        color(col_pin)
            difference() {
                cylinder(h=thick + 2, r=pin_r + 2.5, center=true, $fn=28);
                cylinder(h=thick + 3, r=pin_r + 0.4, center=true, $fn=28);
            }
}

// --- Coupler triangle extension arm ---
module coupler_extension() {
    translate([0, 0, z_coupler])
        bezier_link([Ax, Ay], [Cx, Cy], 5, curve_r * 0.6,
                    col_ext, z_off=0, skew=0.4);
}

// ======== Render: Base Plate ========
color(col_frame)
    translate([a0/2, 10, z_base])
        cube([base_w, base_d, base_t], center=true);

// Ground pivot labels
color([0.7, 0.7, 0.7])
    translate([-12, -18, z_base + base_t/2 + 0.5])
        text("O₀", size=6, halign="center",
             font="Liberation Sans:style=Bold");
color([0.7, 0.7, 0.7])
    translate([a0 + 12, -18, z_base + base_t/2 + 0.5])
        text("O₁", size=6, halign="center",
             font="Liberation Sans:style=Bold");

// ======== Render: Ground Bearings ========
bearing(0, 0);
bearing(a0, 0);

// Straight ground link reference (ghost line)
color(col_ghost, 0.25)
    translate([a0/2, 0, 0])
        cube([a0, 1, 1], center=true);

// ======== Render: Crank (Bezier-curved, red) ========
bezier_link([0, 0], [Ax, Ay], 8, curve_r, col_crank, z_crank);
ctrl_polygon([0, 0], [Ax, Ay], 8, z_ctrl);

// Crank ghost straight line
color(col_ghost, 0.2)
    translate([Ax/2, Ay/2, z_crank])
        rotate([0, 0, theta1])
            cube([a1, 0.5, 0.5], center=true);

// ======== Render: Coupler (Bezier-curved, blue) ========
bezier_link([Ax, Ay], [Bx, By], -14, curve_r, col_coupler, z_coupler);
ctrl_polygon([Ax, Ay], [Bx, By], -14, z_ctrl);

// Coupler triangle extension to trace point
coupler_extension();

// ======== Render: Rocker (Bezier-curved, green) ========
rocker_angle_rad = atan2(By, Bx - a0);
bezier_link([a0, 0], [Bx, By], 10, curve_r, col_rocker, z_rocker, 0.30);
ctrl_polygon([a0, 0], [Bx, By], 10, z_ctrl, 0.30);

// Rocker ghost straight line
color(col_ghost, 0.2) {
    rmx = (a0 + Bx) / 2;
    rmy = By / 2;
    rang = atan2(By, Bx - a0);
    translate([rmx, rmy, z_rocker])
        rotate([0, 0, rang])
            cube([a3, 0.5, 0.5], center=true);
}

// ======== Render: Joint Pins ========
pin_joint(0, 0);
pin_joint(Ax, Ay);
pin_joint(Bx, By);
pin_joint(a0, 0);

// ======== Render: Coupler Trace Point (orange sphere) ========
translate([Cx, Cy, z_ctrl + 2])
    color(col_trace)
        sphere(r=3.5, $fn=24);

// Small stem from coupler to trace sphere
color(col_trace, 0.7)
    translate([Cx, Cy, z_coupler + thick/2])
        cylinder(h=z_ctrl + 2 - z_coupler - thick/2, r=1, $fn=12);

// ======== Render: Full Coupler Trace Path ========
for (i = [0 : n_trace - 1]) {
    t_i = i / n_trace;
    th  = t_i * 360;

    // Recompute kinematics at angle th
    ax_i = a1 * cos(th);
    ay_i = a1 * sin(th);
    ddx  = a0 - ax_i;
    ddy  = -ay_i;
    dd   = sqrt(ddx*ddx + ddy*ddy);
    ss   = (dd*dd + a2*a2 - a3*a3) / (2*dd);
    hh   = sqrt(max(0, a2*a2 - ss*ss));
    uux  = ddx / dd;
    uuy  = ddy / dd;
    bx_i = ax_i + ss*uux - hh*uuy;
    by_i = ay_i + ss*uuy + hh*uux;
    th2  = atan2(by_i - ay_i, bx_i - ax_i);
    cx_i = ax_i + cp_frac*(bx_i - ax_i) - cp_perp*sin(th2);
    cy_i = ay_i + cp_frac*(by_i - ay_i) + cp_perp*cos(th2);

    // Fade trail behind current position
    dt   = $t - t_i;
    fade = dt - floor(dt);
    bright = 0.35 + 0.65 * (1 - fade);

    color([col_trace[0]*bright, col_trace[1]*bright, col_trace[2]*bright])
        translate([cx_i, cy_i, z_ctrl + 2])
            sphere(r=1.2, $fn=10);
}

// ======== Render: Bezier Approximation of Coupler Curve ========
// Sample 4 key positions from the coupler curve as Bezier control points
bez_curve_pts = [for (k = [0:3])
    let(
        tk  = k / 4,
        thk = tk * 360,
        axk = a1 * cos(thk),
        ayk = a1 * sin(thk),
        dxk = a0 - axk,
        dyk = -ayk,
        dk  = sqrt(dxk*dxk + dyk*dyk),
        sk  = (dk*dk + a2*a2 - a3*a3) / (2*dk),
        hk  = sqrt(max(0, a2*a2 - sk*sk)),
        uxk = dxk/dk,
        uyk = dyk/dk,
        bxk = axk + sk*uxk - hk*uyk,
        byk = ayk + sk*uyk + hk*uxk,
        t2k = atan2(byk-ayk, bxk-axk),
        cxk = axk + cp_frac*(bxk-axk) - cp_perp*sin(t2k),
        cyk = ayk + cp_frac*(byk-ayk) + cp_perp*cos(t2k)
    ) [cxk, cyk]
];

// Draw Bezier approximation overlay (purple curve)
color(col_ctrl, 0.55)
    for (j = [0 : n_ctrl - 1]) {
        t0 = j / n_ctrl;
        t1 = (j + 1) / n_ctrl;
        p0 = bez3(bez_curve_pts[0], bez_curve_pts[1],
                   bez_curve_pts[2], bez_curve_pts[3], t0);
        p1 = bez3(bez_curve_pts[0], bez_curve_pts[1],
                   bez_curve_pts[2], bez_curve_pts[3], t1);
        hull() {
            translate([p0[0], p0[1], z_ctrl + 4])
                sphere(r=0.8, $fn=8);
            translate([p1[0], p1[1], z_ctrl + 4])
                sphere(r=0.8, $fn=8);
        }
    }

// Bezier control polygon for coupler curve
for (k = [0 : 3])
    translate([bez_curve_pts[k][0], bez_curve_pts[k][1], z_ctrl + 4])
        color(col_ctrl, 0.8)
            sphere(r=2.0, $fn=14);
for (k = [0 : 2]) {
    mx = (bez_curve_pts[k][0] + bez_curve_pts[k+1][0]) / 2;
    my = (bez_curve_pts[k][1] + bez_curve_pts[k+1][1]) / 2;
    ex = bez_curve_pts[k+1][0] - bez_curve_pts[k][0];
    ey = bez_curve_pts[k+1][1] - bez_curve_pts[k][1];
    el = sqrt(ex*ex + ey*ey);
    ea = atan2(ey, ex);
    color(col_ctrl, 0.3)
        translate([mx, my, z_ctrl + 4])
            rotate([0, 0, ea])
                cube([el, 0.5, 0.5], center=true);
}

// ======== Render: Angle Indicator Arc ========
arc_r = 14;
n_arc = max(1, floor($t * 36));
color([0.95, 0.85, 0.20, 0.7])
    for (i = [0 : n_arc - 1]) {
        a_i = i * 10;
        translate([arc_r * cos(a_i), arc_r * sin(a_i), z_crank])
            sphere(r=0.9, $fn=8);
    }
color([0.95, 0.85, 0.20])
    translate([20, 20, z_crank])
        text(str(floor(theta1), "°"), size=5, halign="left",
             font="Liberation Sans:style=Bold");

// ======== Render: Title ========
color([0.85, 0.85, 0.85])
    translate([a0/2, -base_d/2 + 5, z_base + base_t/2 + 0.5])
        text("Bezier Linkages — Curved Four-Bar Mechanism",
             size=5, halign="center",
             font="Liberation Sans:style=Bold");

// ======== Render: Legend ========
legend_x = base_w/2 + a0/2 - 25;
legend_y = base_d/2 - 5;
module legend_dot(y_off, col, label) {
    translate([legend_x, legend_y - y_off, z_base + base_t/2 + 0.5]) {
        color(col)
            sphere(r=2, $fn=12);
        color([0.7, 0.7, 0.7])
            translate([5, -2, 0])
                text(label, size=4, font="Liberation Sans");
    }
}
legend_dot(0,  col_crank,   "Crank");
legend_dot(8,  col_coupler, "Coupler");
legend_dot(16, col_rocker,  "Rocker");
legend_dot(24, col_trace,   "Trace pt");
legend_dot(32, col_ctrl,    "Bezier ctrl");
