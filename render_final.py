"""blender -b jeju_birth.blend -P render_final.py   -> frames/f_0001.png ..."""
import os, bpy
s = bpy.context.scene
here = os.path.dirname(os.path.abspath(bpy.data.filepath))
s.render.resolution_x, s.render.resolution_y = 1280, 720
s.render.resolution_percentage = 100
s.cycles.samples = 64
s.render.use_overwrite = False        # resumable: skip frames that already exist
s.render.use_placeholder = True
s.render.filepath = os.path.join(here, "frames", "f_")
os.makedirs(os.path.join(here, "frames"), exist_ok=True)
bpy.ops.render.render(animation=True)
