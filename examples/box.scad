// Parametric Box
// Parameters can be overridden with -D on the command line:
//   openscad -D width=50 -D height=30 -D depth=20 -o box.stl box.scad

width  = 30;   // mm
height = 20;   // mm
depth  = 15;   // mm
wall   = 2;    // wall thickness

module parametric_box(w, h, d, t) {
    difference() {
        // Outer shell
        cube([w, d, h], center=true);
        // Inner cavity (open top)
        translate([0, 0, t])
            cube([w - 2*t, d - 2*t, h], center=true);
    }
}

parametric_box(width, height, depth, wall);
