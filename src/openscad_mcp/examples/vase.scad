// Rotational Sweep Vase
// Uses rotate_extrude on a 2-D profile defined by polygon.
// Parameters:
//   base_r   — base radius (mm)
//   top_r    — top rim radius (mm)
//   height   — overall vase height (mm)
//   wall     — wall thickness (mm)
//   bulge    — mid-body outward bulge (mm)

base_r = 20;
top_r  = 15;
height = 60;
wall   = 2.5;
bulge  = 8;

// 2-D cross-section profile (quarter view, will be revolved 360°)
// Points go bottom-to-top along outer wall, then top-to-bottom along inner wall.
module vase_profile(br, tr, h, w, bg) {
    mid_r_outer = max(br, tr) + bg;   // widest point
    mid_h = h * 0.45;                 // height of widest point

    polygon(points=[
        // Outer wall — bottom to top
        [br,     0],
        [mid_r_outer, mid_h],
        [tr,     h],
        // Inner wall — top to bottom
        [tr - w, h],
        [mid_r_outer - w, mid_h],
        [br - w, 0],
    ]);
}

rotate_extrude(angle=360, $fn=128)
    vase_profile(base_r, top_r, height, wall, bulge);
