"""blender -b jeju_birth.blend -P test_render.py -- FRAME PCT SAMPLES OUT"""
import sys, bpy, time
a = sys.argv[sys.argv.index("--") + 1:]
frame, pct, samples, out = int(a[0]), int(a[1]), int(a[2]), a[3]
s = bpy.context.scene
for fr in range(100, frame + 1):   # warm up the particle cache
    s.frame_set(fr)
s.frame_set(frame)
s.render.resolution_percentage = pct
s.cycles.samples = samples
s.render.filepath = out
t = time.time()
bpy.ops.render.render(write_still=True)
print("RENDER_SECONDS", round(time.time() - t, 1))
