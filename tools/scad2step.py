# FreeCAD headless: convert STL mesh -> STEP solid
# env vars: STL_IN=<in.stl> STEP_OUT=<out.step> freecadcmd scad2step.py
# Note: produces a tessellated (faceted) STEP — valid for CAD interchange of
# printed parts, though not smooth parametric surfaces.
import os
import FreeCAD
import Part
import Mesh

stl_in = os.environ["STL_IN"]
step_out = os.environ["STEP_OUT"]

m = Mesh.Mesh(stl_in)
sh = Part.Shape()
sh.makeShapeFromMesh(m.Topology, 0.05)
try:
    solid = Part.makeSolid(sh)
except Exception:
    solid = sh  # open shell; still exportable

# NB: Part.export() wants document objects and writes an empty file for bare
# shapes — exportStep() on the shape itself is the correct call here.
solid.exportStep(step_out)
print("exported", step_out)
