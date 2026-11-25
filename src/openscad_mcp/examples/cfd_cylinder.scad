// ============================================================
// CFD Visualization: Compressible Flow over a Cylinder
// Supersonic freestream M∞ = 2.0 in a channel
// Animated von Kármán vortex street with $t
// ============================================================

// -------------------- Domain --------------------
cyl_r     = 12;
domain_x0 = -90;
domain_x1 = 110;
domain_y0 = -48;
domain_y1 = 48;
domain_w  = domain_x1 - domain_x0;
domain_h  = domain_y1 - domain_y0;

// -------------------- Grid --------------------
nx = 66;
ny = 32;
cell_w = domain_w / nx;
cell_h = domain_h / ny;

// -------------------- Helpers --------------------
function clamp01(v) = min(max(v, 0), 1);
function sigmoid(x) = 1 / (1 + exp(-x));
function sign(x) = x > 0 ? 1 : x < 0 ? -1 : 0;

// -------------------- Colormap --------------------
// Jet: deep blue → cyan → green → yellow → red
function jet(v) =
    let(t = clamp01(v))
    [
        t < 0.38 ? 0 : t < 0.62 ? (t-0.38)/0.24 : 1,
        t < 0.12 ? 0 : t < 0.38 ? (t-0.12)/0.26 :
        t < 0.62 ? 1 : t < 0.88 ? (0.88-t)/0.26 : 0,
        t < 0.38 ? 1 : t < 0.62 ? (0.62-t)/0.24 : 0
    ];

// -------------------- Flow Field --------------------
// Bow shock x-position (parabolic)
function shock_x(y) = -cyl_r * 2.2 + 0.013 * y * y;

// Mach-like flow field: 0 = stagnation, 1 = max supersonic
function flow_val(x, y, t) =
    let(
        r  = sqrt(x*x + y*y),
        th = atan2(y, x),
        sx = shock_x(y),

        // Smooth shock transition (upstream=0, downstream=1)
        st = sigmoid((x - sx) * 0.7),

        // Base value: freestream (0.74) upstream, subsonic (0.30) post-shock
        base = 0.74 * (1 - st) + 0.30 * st,

        // Stagnation dip near front face of cylinder
        sd2  = (x + cyl_r)*(x + cyl_r) + y*y,
        stag = 0.22 * exp(-sd2 / 160),

        // Shock ridge (bright band along shock front)
        dsx    = x - sx,
        sridge = (dsx > 0 && dsx < 10) ? 0.08 * exp(-dsx*dsx/18) : 0,

        // Expansion around cylinder sides (high Mach → high value)
        ang = abs(th),
        efact = (r > cyl_r && r < cyl_r*4 && ang > 35 && ang < 155) ?
            0.38 * exp(-(r - cyl_r*1.3)*(r - cyl_r*1.3)/220) *
            pow(sin(clamp01((ang-35)/120) * 90), 1.4) : 0,

        // Reflected shocks off channel walls (faint ridges)
        // Approximate reflection points where bow shock hits walls
        ref_x_top = shock_x(domain_y1),
        ref_x_bot = shock_x(domain_y0),
        // Reflected shock angle ~40°
        ref_shock_1 = x - ref_x_top - (domain_y1 - y) * 0.84,
        ref_shock_2 = x - ref_x_bot - (y - domain_y0) * 0.84,
        rshock1 = (ref_shock_1 > -2 && ref_shock_1 < 8 && y < domain_y1 * 0.7) ?
            0.06 * exp(-ref_shock_1*ref_shock_1/12) : 0,
        rshock2 = (ref_shock_2 > -2 && ref_shock_2 < 8 && y > domain_y0 * 0.7) ?
            0.06 * exp(-ref_shock_2*ref_shock_2/12) : 0,

        // Wake deficit behind cylinder
        ww = max(cyl_r * 0.9 + max(x - cyl_r, 0) * 0.04, 1),
        wake = (x > cyl_r * 0.5) ?
            0.16 * exp(-y*y/(2*ww*ww)) * exp(-max(x-cyl_r, 0)/60) : 0,

        // Von Kármán vortex street (animated)
        vp  = x * 0.09 - t * 360,
        vys = cyl_r * 0.7 * sin(vp),
        vort = (x > cyl_r * 2) ?
            0.13 * sin(vp + 90) *
            exp(-(y - vys)*(y - vys)/(cyl_r*cyl_r*1.4)) *
            (1 - exp(-(x - cyl_r*2)/15)) *
            exp(-max(x - cyl_r*2, 0)/60) : 0,

        // Secondary vortex row (opposite phase, offset)
        vp2  = x * 0.09 - t * 360 + 180,
        vys2 = -cyl_r * 0.5 * sin(vp2),
        vort2 = (x > cyl_r * 3) ?
            0.07 * sin(vp2 + 90) *
            exp(-(y - vys2)*(y - vys2)/(cyl_r*cyl_r*2)) *
            (1 - exp(-(x - cyl_r*3)/20)) *
            exp(-max(x - cyl_r*3, 0)/55) : 0,

        // Recovery toward freestream far from cylinder
        rec = clamp01((r - cyl_r*4) / (cyl_r*3)),

        // Combine
        val = (base - stag + sridge + efact + rshock1 + rshock2
               - wake + vort + vort2) * (1 - rec) + 0.74 * rec
    )
    (r < cyl_r) ? -1 : clamp01(val);

// ==================== SCENE ====================

// ---- Contour tiles ----
for (i = [0 : nx-1])
    for (j = [0 : ny-1]) {
        cx = domain_x0 + (i + 0.5) * cell_w;
        cy = domain_y0 + (j + 0.5) * cell_h;
        fv = flow_val(cx, cy, $t);
        if (fv >= 0)
            color(jet(fv))
                translate([cx, cy, -0.5])
                    cube([cell_w + 0.15, cell_h + 0.15, 1], center=true);
    }

// ---- Mesh grid overlay (faint) ----
color([0, 0, 0, 0.08]) {
    for (i = [0 : 10 : nx])
        translate([domain_x0 + i * cell_w, 0, 0.3])
            cube([0.15, domain_h, 0.05], center=true);
    for (j = [0 : 8 : ny])
        translate([domain_x0 + domain_w/2, domain_y0 + j * cell_h, 0.3])
            cube([domain_w, 0.15, 0.05], center=true);
}

// ---- Cylinder (3D, metallic) ----
color([0.50, 0.50, 0.55])
    cylinder(r=cyl_r, h=6, center=true, $fn=64);
color([0.60, 0.60, 0.65])
    translate([0, 0, 3.2])
        cylinder(r=cyl_r + 0.3, h=0.5, center=true, $fn=64);
color([0.60, 0.60, 0.65])
    translate([0, 0, -3.2])
        cylinder(r=cyl_r + 0.3, h=0.5, center=true, $fn=64);

// ---- Channel walls ----
wall_h = 8;
color([0.55, 0.55, 0.60]) {
    translate([domain_x0 + domain_w/2, domain_y1 + 2.5, wall_h/2 - 1])
        cube([domain_w + 6, 5, wall_h], center=true);
    translate([domain_x0 + domain_w/2, domain_y0 - 2.5, wall_h/2 - 1])
        cube([domain_w + 6, 5, wall_h], center=true);
}
// Wall top caps
color([0.65, 0.65, 0.70]) {
    translate([domain_x0 + domain_w/2, domain_y1 + 2.5, wall_h - 1])
        cube([domain_w + 6, 5.5, 0.5], center=true);
    translate([domain_x0 + domain_w/2, domain_y0 - 2.5, wall_h - 1])
        cube([domain_w + 6, 5.5, 0.5], center=true);
}

// ---- Inlet arrows (left edge) ----
for (a = [-3 : 3]) {
    ay = a * 12;
    if (abs(ay) < domain_h/2 - 5)
        color([1, 1, 1, 0.5])
            translate([domain_x0 - 4, ay, 1]) {
                cube([8, 0.8, 0.8], center=true);
                translate([5, 0, 0])
                    rotate([0, 0, 0])
                        cylinder(h=0.8, r1=2, r2=0, center=true, $fn=3);
            }
}

// ---- Color legend ----
legend_x = domain_x1 + 10;
legend_h = domain_h * 0.65;
legend_y0 = domain_y0 + domain_h * 0.175;
n_legend = 30;
for (k = [0 : n_legend - 1]) {
    v = k / (n_legend - 1);
    color(jet(v))
        translate([legend_x, legend_y0 + v * legend_h, 0])
            cube([6, legend_h/n_legend + 0.2, 2], center=true);
}
// Legend border
color([0.3, 0.3, 0.35]) {
    translate([legend_x, legend_y0 + legend_h/2, 0.5])
        difference() {
            cube([7, legend_h + 2, 0.3], center=true);
            cube([5.5, legend_h - 0.5, 1], center=true);
        }
}
// Legend labels
color([0.85, 0.85, 0.90]) {
    translate([legend_x + 6, legend_y0 - 2, 0])
        linear_extrude(1) text("0.0", size=3, halign="left", font="Liberation Sans");
    translate([legend_x + 6, legend_y0 + legend_h/2 - 1.5, 0])
        linear_extrude(1) text("1.4", size=3, halign="left", font="Liberation Sans");
    translate([legend_x + 6, legend_y0 + legend_h - 1, 0])
        linear_extrude(1) text("2.8", size=3, halign="left", font="Liberation Sans");
    translate([legend_x, legend_y0 + legend_h + 5, 0])
        linear_extrude(1) text("Mach", size=3.5, halign="center",
            font="Liberation Sans:style=Bold");
}

// ---- Title ----
color([0.90, 0.90, 0.95])
    translate([domain_x0 + domain_w/2, domain_y1 + 12, wall_h])
        linear_extrude(1)
            text("Supersonic Flow over Cylinder  M∞ = 2.0",
                 size=5, halign="center",
                 font="Liberation Sans:style=Bold");

// ---- Info text ----
color([0.70, 0.70, 0.75])
    translate([domain_x0 + domain_w/2, domain_y0 - 12, 0])
        linear_extrude(0.5)
            text("Compressible RANS  |  Channel H/D = 4.0  |  Re = 1×10⁶",
                 size=3, halign="center", font="Liberation Sans");

// ---- Flow particles (animated streamlines) ----
num_streams = 16;
pts_per_stream = 6;
for (s = [0 : num_streams - 1]) {
    py0 = domain_y0 + (s + 0.5) * domain_h / num_streams;
    if (abs(py0) > cyl_r + 4) {
        for (p = [0 : pts_per_stream - 1]) {
            // Particle x wraps across domain
            px_raw = domain_x0 + 10 +
                     (($t * 180 + s * 12 + p * 28) % domain_w);
            px = (px_raw > domain_x1) ? px_raw - domain_w : px_raw;
            // Deflect around cylinder using potential flow approximation
            r2 = px*px + py0*py0;
            py = (r2 > 0.01) ?
                py0 / (1 - cyl_r*cyl_r / max(r2, cyl_r*cyl_r*1.2)) : py0;
            // Clamp to domain
            py_c = min(max(py, domain_y0 + 2), domain_y1 - 2);
            // Only show if not inside cylinder
            r_check = sqrt(px*px + py_c*py_c);
            if (r_check > cyl_r + 2)
                color([1, 1, 1, 0.45])
                    translate([px, py_c, 1.5])
                        sphere(r=1, $fn=6);
        }
    }
}
