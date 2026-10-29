"""blender -b -P encode_video.py  -> jeju_birth.mp4 (H.264, 24 fps) from frames/f_####.png"""
import os, glob, bpy
here = os.path.dirname(os.path.abspath(__file__))
files = sorted(glob.glob(os.path.join(here, "frames", "f_*.png")))
print("frames:", len(files))
bpy.ops.wm.read_factory_settings(use_empty=True)
s = bpy.context.scene
s.render.resolution_x, s.render.resolution_y = 1280, 720
s.render.resolution_percentage = 100
s.render.fps = 24
s.frame_start, s.frame_end = 1, len(files)
s.sequence_editor_create()
strips = s.sequence_editor.strips
st = strips.new_image("seq", files[0], channel=1, frame_start=1)
for f in files[1:]:
    st.elements.append(os.path.basename(f))
r = s.render
r.image_settings.media_type = "VIDEO"
r.image_settings.file_format = "FFMPEG"
r.ffmpeg.format = "MPEG4"
r.ffmpeg.codec = "H264"
r.ffmpeg.constant_rate_factor = "HIGH"
r.ffmpeg.ffmpeg_preset = "GOOD"
r.ffmpeg.audio_codec = "NONE"
r.filepath = os.path.join(here, "jeju_birth.mp4")
s.view_settings.view_transform = "Standard"      # frames are already tone-mapped
bpy.ops.render.render(animation=True)
print("done")
