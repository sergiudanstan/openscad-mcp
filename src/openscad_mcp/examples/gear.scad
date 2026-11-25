// Simple Spur Gear (illustrative — uses cylinders for teeth)
// Parameters:
//   teeth      — number of gear teeth
//   pitch_r    — pitch radius (mm)
//   tooth_h    — tooth height (mm)
//   thickness  — gear thickness (mm)
//   bore_r     — center bore radius (mm)

teeth     = 12;
pitch_r   = 20;
tooth_h   = 3;
thickness = 5;
bore_r    = 4;

tooth_r   = tooth_h / 2;            // radius of each tooth cylinder
tooth_pos = pitch_r + tooth_r;      // distance from center to tooth center

module gear(t, pr, th, tk, br) {
    difference() {
        union() {
            // Gear body disc
            cylinder(h=tk, r=pr, center=true, $fn=64);

            // Teeth arranged around the circumference
            for (i = [0 : t - 1]) {
                rotate([0, 0, i * (360 / t)])
                    translate([pr + th/2, 0, 0])
                        cylinder(h=tk, r=th/2, center=true, $fn=16);
            }
        }
        // Center bore
        cylinder(h=tk + 1, r=br, center=true, $fn=32);
    }
}

gear(teeth, pitch_r, tooth_h, thickness, bore_r);
