// ============================================================
//  ROVER CHASSIS  -  v1 (first draft, fully parametric)
//  For: Freenove-style 4WD rover, Raspberry Pi brain
//  Sized to leave room for a Pi UPGRADE (Pi 4 / Pi 5 footprint)
//  Units = millimetres.  Print flat on the bed, deck-side down.
// ============================================================

// ---------- MASTER PARAMETERS (tweak these) ----------
deck_len      = 210;   // front-to-back
deck_wid      = 150;   // left-to-right
deck_thick    = 4;     // plate thickness
corner_r      = 10;    // rounded corners

// TT gear motor (the yellow ones) - standard-ish dims
motor_body_l  = 70;    // full length of motor+gearbox
motor_body_w  = 22.5;  // width of gearbox
motor_cradle_h= 14;    // height of the cradle walls
motor_wall    = 3;     // cradle wall thickness

// Raspberry Pi mounting - Pi 4 / Pi 5 hole pattern (UPGRADE-ready)
pi_hole_x     = 58;    // hole spacing long axis
pi_hole_y     = 49;    // hole spacing short axis
pi_hole_d     = 2.7;   // for M2.5 screws / self-tappers
pi_boss_d     = 7;     // standoff boss outer dia
pi_boss_h     = 6;     // standoff height (lifts board off deck)

// Motor driver / HAT board (generic 4-hole board)
drv_hole_x    = 50;
drv_hole_y    = 30;
drv_hole_d    = 2.7;

// 2x 18650 battery holder pocket (typical holder ~ 78 x 40 mm)
batt_l        = 80;
batt_w        = 42;
batt_wall     = 2.5;
batt_wall_h   = 8;

// Camera mast at the front (uprights the pan/tilt bolts to)
cam_post_h    = 55;
cam_post_w    = 12;
cam_post_t    = 6;
cam_gap       = 30;    // gap between the two uprights
cam_hole_d    = 2.7;

// Lightening / wiring holes
light_hole_d  = 14;
$fn           = 48;

// ============================================================
//  HELPER MODULES
// ============================================================
module rrect(l, w, r, h) {              // rounded-rect prism
    linear_extrude(h)
        offset(r=r) offset(r=-r)
            square([l, w], center=true);
}

module screw_boss(d_out, d_in, h) {     // standoff w/ pilot hole
    difference() {
        cylinder(d=d_out, h=h);
        translate([0,0,-0.1]) cylinder(d=d_in, h=h+0.2);
    }
}

// Motor cradle: U-channel that a TT motor drops into + screw slots
module motor_cradle() {
    difference() {
        union() {
            // two side walls (built up from z=0 so they sit ON the deck)
            for (s=[-1,1])
                translate([-motor_body_l/2, s*(motor_body_w/2 + motor_wall/2) - motor_wall/2, 0])
                    cube([motor_body_l, motor_wall, motor_cradle_h]);
        }
        // screw slots through the walls (for the motor's mount screws)
        for (x=[-motor_body_l/2+12, motor_body_l/2-12])
            for (s=[-1,1])
                translate([x, s*(motor_body_w/2+motor_wall), motor_cradle_h*0.35])
                    rotate([90,0,0])
                        cylinder(d=3.2, h=motor_wall*3, center=true);
    }
}

// Camera mast upright with two mounting holes
module cam_post() {
    difference() {
        cube([cam_post_t, cam_post_w, cam_post_h]);
        for (z=[cam_post_h*0.55, cam_post_h*0.82])
            translate([-0.1, cam_post_w/2, z])
                rotate([0,90,0]) cylinder(d=cam_hole_d, h=cam_post_t+0.2);
    }
}

// ============================================================
//  MAIN ASSEMBLY
// ============================================================
module chassis() {
    difference() {
        union() {
            // --- main deck ---
            rrect(deck_len, deck_wid, corner_r, deck_thick);

            // --- Pi standoff bosses (upgrade-ready Pi 4/5 pattern) ---
            translate([ -25, 0, deck_thick ])   // Pi sits center-rear
                for (sx=[-1,1]) for (sy=[-1,1])
                    translate([sx*pi_hole_x/2, sy*pi_hole_y/2, 0])
                        screw_boss(pi_boss_d, pi_hole_d, pi_boss_h);

            // --- motor driver board bosses ---
            translate([ 55, 0, deck_thick ])
                for (sx=[-1,1]) for (sy=[-1,1])
                    translate([sx*drv_hole_x/2, sy*drv_hole_y/2, 0])
                        screw_boss(pi_boss_d, drv_hole_d, pi_boss_h);

            // --- 4 motor cradles at the corners ---
            for (sx=[-1,1]) for (sy=[-1,1])
                translate([ sx*(deck_len/2 - motor_body_l/2 - 4),
                            sy*(deck_wid/2 - motor_body_w/2 - motor_wall - 2),
                            deck_thick ])
                    motor_cradle();

            // --- battery pocket walls (center) ---
            translate([0,0,deck_thick])
            difference() {
                rrect(batt_l+2*batt_wall, batt_w+2*batt_wall, 4, batt_wall_h);
                translate([0,0,-0.1])
                    rrect(batt_l, batt_w, 3, batt_wall_h+0.2);
            }

            // --- camera mast uprights at the very front ---
            translate([deck_len/2 - cam_post_t - 3, -cam_gap/2 - cam_post_w, deck_thick])
                cam_post();
            translate([deck_len/2 - cam_post_t - 3,  cam_gap/2, deck_thick])
                cam_post();
        }

        // ---------- CUTOUTS ----------
        // lightening + wiring holes in a grid (skip where features sit)
        for (gx=[-1:1]) for (gy=[-1:1])
            if (!(gx==0))   // keep center clear for battery
                translate([gx*60, gy*45, -0.1])
                    cylinder(d=light_hole_d, h=deck_thick+0.2);

        // front wiring slot
        translate([deck_len/2-30, 0, -0.1])
            rrect(10, 40, 4, deck_thick+0.2);
    }
}

chassis();
