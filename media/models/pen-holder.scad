// Universal cable-tie attachment prototype. Measure your pen and check
// clearance against the actual Ender-3 Neo head, CR Touch and bed clips.
pen_diameter = 9;
clip_height = 18;
wall = 3;
clearance = 0.3;
$fn = 192;
r = pen_diameter / 2 + clearance;
cx = r + 1;

difference() {
    union() {
        translate([-28, -9, 0]) cube([28, 18, clip_height]);
        translate([cx, 0, 0]) cylinder(h=clip_height, r=r+wall);
    }
    translate([cx, 0, -1]) cylinder(h=clip_height+2, r=r);
    translate([cx, -0.7, -1]) cube([r+4, 1.4, clip_height+2]);
    for (y = [-6, 3])
        translate([-23, y, -1]) cube([4, 3, clip_height+2]);
}
