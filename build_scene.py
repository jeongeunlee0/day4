"""Build the 'Birth of Jeju Island' animation scene from the Jeju DEM.
Run:  blender -b -P build_scene.py     -> jeju_birth.blend
Units: 1 Blender unit = 1 km (horizontal); heights are exaggerated x EX.
"""
import os, json, math
import numpy as np
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
meta = json.load(open(os.path.join(HERE, "dem", "jeju_meta.json")))
dem = np.load(os.path.join(HERE, "dem", "jeju_dem.npy"))  # row 0 = north

EX = 3.0                 # vertical exaggeration
FLOOR_M = -130.0         # flat sea floor (m)
F_END = 300
FPS = 24
SUN_ELEV = 12.0
SUN_AZ = 24.0           # degrees (tuned by test renders)
HX, HY = meta["hallasan_km"]

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
scn.frame_start, scn.frame_end = 1, F_END
scn.render.fps = FPS


def z_of(h_m):
    return h_m / 1000.0 * EX


# ---------------------------------------------------------------- terrain mesh
ny, nx = dem.shape
h_c = np.maximum(dem, FLOOR_M)
# soften the DEM a touch to remove SRTM speckle on the mesh
from numpy import pad
k = np.array([1, 2, 1], dtype=np.float32) / 4
def blur(a):
    p = np.pad(a, 1, mode="edge")
    a = p[1:-1, :-2] * k[0] + p[1:-1, 1:-1] * k[1] + p[1:-1, 2:] * k[2]
    p = np.pad(a, ((1, 1), (0, 0)), mode="edge")
    return p[:-2] * k[0] + p[1:-1] * k[1] + p[2:] * k[2]
h_c = blur(h_c)
# fade the outer margin to the flat floor so the DEM tile has no visible edge
yy, xx = np.mgrid[0:ny, 0:nx]
edge = np.minimum.reduce([xx, nx - 1 - xx, yy, ny - 1 - yy]).astype(np.float32)
w = np.clip(edge / 28.0, 0, 1)
w = w * w * (3 - 2 * w)
h_c = FLOOR_M + (h_c - FLOOR_M) * w

xs = (np.linspace(-0.5, 0.5, nx) * meta["km_w"]).astype(np.float32)
ys = (np.linspace(0.5, -0.5, ny) * meta["km_h"]).astype(np.float32)
X, Y = np.meshgrid(xs, ys)

h_A = np.minimum(h_c, -12.0)                                 # undersea volcano nearly reaching the surface
h_B = np.where(h_c > 0, h_c * 0.30, h_c)                     # low shield island
h_B = np.maximum(h_B, h_A)
h_C = h_c                                                    # present-day relief incl. Hallasan
h_B = np.where(h_C > h_B, h_B, h_C)
h_A = np.minimum(h_A, h_B)

def verts(hm):
    return np.stack([X.ravel(), Y.ravel(), z_of(hm).ravel()], axis=1).astype(np.float32)

idx = np.arange(nx * ny).reshape(ny, nx)
quads = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], axis=-1).reshape(-1, 4)

mesh = bpy.data.meshes.new("JejuMesh")
mesh.from_pydata(verts(np.full_like(h_c, FLOOR_M)).tolist(), [], quads.tolist())
mesh.shade_smooth()
terrain = bpy.data.objects.new("Jeju", mesh)
scn.collection.objects.link(terrain)
terrain.shape_key_add(name="Basis", from_mix=False)
keys = []
prev = terrain.data.shape_keys.key_blocks["Basis"]
for name, hm in (("A_seamount", h_A), ("B_shield", h_B), ("C_hallasan", h_C)):
    kb = terrain.shape_key_add(name=name, from_mix=False)
    kb.data.foreach_set("co", verts(hm).ravel())
    kb.relative_key = prev
    prev = kb
    keys.append(kb)

# eruption stage timing (frame ranges)
STAGES = [(1, 78), (62, 150), (128, 238)]
for kb, (a, b) in zip(keys, STAGES):
    kb.value = 0.0
    kb.keyframe_insert("value", frame=a - 1 if a > 1 else 1)
    kb.value = 1.0
    kb.keyframe_insert("value", frame=b)


def summit_z(f):
    """z (BU) of the Hallasan summit at frame f."""
    scn.frame_set(f)
    i = int(round((0.5 - HY / meta["km_h"]) * (ny - 1)))
    j = int(round((HX / meta["km_w"] + 0.5) * (nx - 1)))
    z0 = z_of(FLOOR_M)
    za, zb, zc = (z_of(h[i, j]) for h in (h_A, h_B, h_C))
    va, vb, vc = (kb.value for kb in keys)
    z = z0 + (za - z0) * va
    z += (zb - za) * vb
    z += (zc - zb) * vc
    return z


# floor plane (infinite sea bed)
bpy.ops.mesh.primitive_plane_add(size=4000, location=(0, 0, z_of(FLOOR_M) - 0.004))
floor = bpy.context.object
floor.name = "SeaBed"


# ---------------------------------------------------------------- node helpers
def N(tree, typ, x=0, y=0, **props):
    n = tree.nodes.new(typ)
    n.location = (x, y)
    for k_, v in props.items():
        setattr(n, k_, v)
    return n


def L(tree, a, b):
    tree.links.new(a, b)


def val_node(tree, v=0.0, label=None):
    n = N(tree, "ShaderNodeValue")
    n.outputs[0].default_value = v
    if label:
        n.label = n.name = label
    return n


def keys_on(node, pts):
    for f, v in pts:
        node.outputs[0].default_value = v
        node.outputs[0].keyframe_insert("default_value", frame=f)


def ramp(tree, stops, interp="LINEAR"):
    r = N(tree, "ShaderNodeValToRGB")
    r.color_ramp.interpolation = interp
    el = r.color_ramp.elements
    while len(el) < len(stops):
        el.new(0.5)
    for e, (p, c) in zip(el, stops):
        e.position = p
        e.color = c
    return r


def mixrgb(tree, fac, a, b):
    m = N(tree, "ShaderNodeMix", data_type="RGBA")
    if isinstance(fac, (int, float)):
        m.inputs[0].default_value = fac
    else:
        L(tree, fac, m.inputs[0])
    for i, s in ((6, a), (7, b)):
        if isinstance(s, (tuple, list)):
            m.inputs[i].default_value = s
        else:
            L(tree, s, m.inputs[i])
    return m.outputs[2]


def maprange(tree, src, a0, a1, b0=0.0, b1=1.0, clamp=True):
    m = N(tree, "ShaderNodeMapRange")
    m.clamp = clamp
    m.inputs[1].default_value, m.inputs[2].default_value = a0, a1
    m.inputs[3].default_value, m.inputs[4].default_value = b0, b1
    if src is not None:
        L(tree, src, m.inputs[0])
    return m


def math_(tree, op, a, b=None, clamp=False):
    m = N(tree, "ShaderNodeMath", operation=op, use_clamp=clamp)
    for i, s in ((0, a), (1, b)):
        if s is None:
            continue
        if isinstance(s, (int, float)):
            m.inputs[i].default_value = s
        else:
            L(tree, s, m.inputs[i])
    return m.outputs[0]


# ---------------------------------------------------------------- terrain material
mat = bpy.data.materials.new("JejuTerrain")
mat.use_nodes = True
t = mat.node_tree
for n in list(t.nodes):
    t.nodes.remove(n)
out = N(t, "ShaderNodeOutputMaterial")
bsdf = N(t, "ShaderNodeBsdfPrincipled")
bsdf.inputs["Roughness"].default_value = 0.88
geo = N(t, "ShaderNodeNewGeometry")
sep = N(t, "ShaderNodeSeparateXYZ")
L(t, geo.outputs["Position"], sep.inputs[0])
zbu = sep.outputs[2]
hm_norm = maprange(t, zbu, 0.0, z_of(1950.0))          # 0..1 over elevation
nrm_sep = N(t, "ShaderNodeSeparateXYZ")
L(t, geo.outputs["Normal"], nrm_sep.inputs[0])
steep = maprange(t, nrm_sep.outputs[2], 0.80, 0.55)     # 0 flat -> 1 cliff

noise_big = N(t, "ShaderNodeTexNoise", noise_dimensions="3D")
noise_big.inputs["Scale"].default_value = 0.35
noise_big.inputs["Detail"].default_value = 6
L(t, geo.outputs["Position"], noise_big.inputs["Vector"])
noise_fine = N(t, "ShaderNodeTexNoise", noise_dimensions="3D")
noise_fine.inputs["Scale"].default_value = 3.0
noise_fine.inputs["Detail"].default_value = 8
L(t, geo.outputs["Position"], noise_fine.inputs["Vector"])
nb, nf = noise_big.outputs["Fac"], noise_fine.outputs["Fac"]

veg_ramp = ramp(t, [
    (0.00, (0.10, 0.20, 0.035, 1)),
    (0.18, (0.05, 0.16, 0.03, 1)),
    (0.50, (0.025, 0.08, 0.03, 1)),
    (0.78, (0.16, 0.13, 0.08, 1)),
    (1.00, (0.30, 0.28, 0.26, 1)),
])
L(t, math_(t, "ADD", hm_norm.outputs[0], math_(t, "MULTIPLY", math_(t, "SUBTRACT", nb, 0.5), 0.35)),
  veg_ramp.inputs[0])
rock_col = (0.17, 0.15, 0.14, 1)
veg_col = mixrgb(t, steep.outputs[0], veg_ramp.outputs[0], rock_col)

basalt_ramp = ramp(t, [(0.0, (0.012, 0.010, 0.010, 1)), (0.55, (0.04, 0.03, 0.028, 1)), (1.0, (0.16, 0.06, 0.035, 1))])
L(t, nf, basalt_ramp.inputs[0])
bare = basalt_ramp.outputs[0]

# vegetation spreading over time
veg_amt = val_node(t, 0.0, "veg_amt")
keys_on(veg_amt, [(1, 0.0), (205, 0.0), (300, 1.0)])
veg_drive = math_(t, "SUBTRACT",
                  math_(t, "MULTIPLY", veg_amt.outputs[0], 1.7),
                  math_(t, "ADD", math_(t, "MULTIPLY", nb, 0.7), math_(t, "MULTIPLY", hm_norm.outputs[0], 0.35)))
veg_fac = maprange(t, veg_drive, 0.0, 0.35)
surf_col = mixrgb(t, veg_fac.outputs[0], bare, veg_col)

# sand / surf band and underwater tint
sand = maprange(t, zbu, 0.007, 0.002)
sand_m = math_(t, "MULTIPLY", sand.outputs[0], maprange(t, zbu, -0.03, 0.0).outputs[0])
col1 = mixrgb(t, sand_m, surf_col, (0.42, 0.37, 0.27, 1))
foam_band = math_(t, "MULTIPLY", maprange(t, zbu, 0.002, -0.004).outputs[0], maprange(t, zbu, -0.03, -0.008).outputs[0])
col2 = mixrgb(t, foam_band, col1, (0.9, 0.95, 1.0, 1))
depth_ramp = ramp(t, [(0.0, (0.07, 0.30, 0.30, 1)), (0.30, (0.02, 0.14, 0.24, 1)), (1.0, (0.004, 0.025, 0.07, 1))])
L(t, maprange(t, zbu, -0.003, z_of(FLOOR_M)).outputs[0], depth_ramp.inputs[0])
under = maprange(t, zbu, 0.002, -0.012)
base_col = mixrgb(t, under.outputs[0], col2, mixrgb(t, 0.45, col2, depth_ramp.outputs[0]))
# below the water the tint dominates
base_col = mixrgb(t, under.outputs[0], col2, depth_ramp.outputs[0])
L(t, base_col, bsdf.inputs["Base Color"])

# ---- lava
pos_sep = sep
comb = N(t, "ShaderNodeCombineXYZ")
L(t, pos_sep.outputs[0], comb.inputs[0])
L(t, pos_sep.outputs[1], comb.inputs[1])
dist = N(t, "ShaderNodeVectorMath", operation="DISTANCE")
L(t, comb.outputs[0], dist.inputs[0])
dist.inputs[1].default_value = (HX, HY, 0.0)
lava_noise = N(t, "ShaderNodeTexNoise", noise_dimensions="3D")
lava_noise.inputs["Scale"].default_value = 0.22
lava_noise.inputs["Detail"].default_value = 5
L(t, geo.outputs["Position"], lava_noise.inputs["Vector"])
R = val_node(t, 0.0, "lava_R")
keys_on(R, [(1, 0.0), (10, 3.0), (78, 14.0), (150, 16.0), (238, 22.0), (300, 23.0)])
dist_w = math_(t, "ADD", dist.outputs["Value"], math_(t, "MULTIPLY", math_(t, "SUBTRACT", lava_noise.outputs["Fac"], 0.5), 14.0))
lava_m = maprange(t, math_(t, "SUBTRACT", R.outputs[0], dist_w), 0.0, 2.0)
# long streaks of fresh lava: thin bright veins
vein = N(t, "ShaderNodeTexNoise", noise_dimensions="3D")
vein.inputs["Scale"].default_value = 0.9
vein.inputs["Detail"].default_value = 4
L(t, geo.outputs["Position"], vein.inputs["Vector"])
lava_col = ramp(t, [(0.0, (0.0, 0.0, 0.0, 1)), (0.52, (0.25, 0.01, 0.0, 1)), (0.60, (1.0, 0.22, 0.02, 1)), (0.75, (1.0, 0.65, 0.18, 1))])
L(t, vein.outputs["Fac"], lava_col.inputs[0])
hot = val_node(t, 0.0, "lava_hot")
keys_on(hot, [(1, 0.0), (22, 1.0), (215, 1.0), (275, 0.0), (300, 0.0)])
em = N(t, "ShaderNodeEmission")
em.inputs["Strength"].default_value = 1.0
L(t, lava_col.outputs[0], em.inputs["Color"])
em_str = math_(t, "MULTIPLY", math_(t, "MULTIPLY", lava_m.outputs[0], hot.outputs[0]), 16.0)
# fresh-lava glow only where the vein pattern is bright
L(t, em_str, em.inputs["Strength"])
# lava turns terrain to black basalt
flow_dark = lava_m.outputs[0]
L(t, mixrgb(t, math_(t, "MULTIPLY", flow_dark, 0.9), base_col, (0.012, 0.010, 0.010, 1)), bsdf.inputs["Base Color"])
add = N(t, "ShaderNodeAddShader")
L(t, bsdf.outputs[0], add.inputs[0])
L(t, em.outputs[0], add.inputs[1])
L(t, add.outputs[0], out.inputs["Surface"])
terrain.data.materials.append(mat)
floor.data.materials.append(mat)

# ---------------------------------------------------------------- ocean
OCEAN_SCALE = 0.08
OCEAN_TILE = 600
OCEAN_REPEAT = 11
water = bpy.data.materials.new("Water")
water.use_nodes = True
w_ = water.node_tree
for n in list(w_.nodes):
    w_.nodes.remove(n)
w_out = N(w_, "ShaderNodeOutputMaterial")
wb = N(w_, "ShaderNodeBsdfPrincipled")
wb.inputs["Base Color"].default_value = (0.02, 0.17, 0.24, 1)
wb.inputs["Roughness"].default_value = 0.025
wb.inputs["IOR"].default_value = 1.333
wb.inputs["Transmission Weight"].default_value = 0.9
wb.inputs["Specular IOR Level"].default_value = 0.6
tc = N(w_, "ShaderNodeTexCoord")
mp = N(w_, "ShaderNodeMapping")
L(w_, tc.outputs["Object"], mp.inputs[0])
ripple = N(w_, "ShaderNodeTexNoise", noise_dimensions="4D")
ripple.inputs["Scale"].default_value = 0.55
ripple.inputs["Detail"].default_value = 6
ripple.inputs["Roughness"].default_value = 0.6
L(w_, mp.outputs[0], ripple.inputs["Vector"])
drv = w_.driver_add(f'nodes["{ripple.name}"].inputs["W"].default_value')
drv.driver.expression = "frame*0.05"
bump = N(w_, "ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.22
bump.inputs["Distance"].default_value = 0.05
L(w_, ripple.outputs["Fac"], bump.inputs["Height"])
L(w_, bump.outputs["Normal"], wb.inputs["Normal"])
# foam
fa = N(w_, "ShaderNodeAttribute", attribute_name="foam", attribute_type="GEOMETRY")
fr = ramp(w_, [(0.85, (0, 0, 0, 1)), (1.0, (1, 1, 1, 1))])
L(w_, fa.outputs["Fac"], fr.inputs[0])
foam_sh = N(w_, "ShaderNodeBsdfDiffuse")
foam_sh.inputs["Color"].default_value = (0.85, 0.9, 0.92, 1)
mixs = N(w_, "ShaderNodeMixShader")
L(w_, fr.outputs[0], mixs.inputs[0])
L(w_, wb.outputs[0], mixs.inputs[1])
L(w_, foam_sh.outputs[0], mixs.inputs[2])
L(w_, wb.outputs[0], w_out.inputs["Surface"])   # mesh foam disabled (too blocky); shoreline surf is on the terrain

bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, 0))
ocean = bpy.context.object
ocean.name = "Ocean"
ocean.scale = (OCEAN_SCALE, OCEAN_SCALE, OCEAN_SCALE)
om = ocean.modifiers.new("Ocean", "OCEAN")
om.geometry_mode = "GENERATE"
om.resolution = 12
om.viewport_resolution = 4
om.spatial_size = OCEAN_TILE
om.repeat_x = om.repeat_y = OCEAN_REPEAT
_c = (OCEAN_REPEAT - 1) * OCEAN_TILE / 2 * OCEAN_SCALE      # generated grid starts at a tile corner
ocean.location = (-_c, -_c, 0.0)
om.wave_scale = 1.0
om.choppiness = 1.5
om.wind_velocity = 12.0
om.wave_alignment = 0.4
om.wave_direction = math.radians(-60)
om.damping = 0.4
om.depth = 400
om.random_seed = 7
om.use_foam = True
om.foam_coverage = 0.05
om.foam_layer_name = "foam"
om.use_normals = True
ocean.data.materials.append(water)
om.time = 0.0
om.keyframe_insert("time", frame=1)
om.time = 22.0
om.keyframe_insert("time", frame=F_END)
for fc in ocean.animation_data.action.fcurves if hasattr(ocean.animation_data.action, "fcurves") else []:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"

# far ocean (unrippled) to reach the horizon
bpy.ops.mesh.primitive_plane_add(size=6000, location=(0, 0, -0.3))
far = bpy.context.object
far.name = "OceanFar"
far.scale = (30, 30, 1)
far_mat = water.copy()
far_mat.name = "WaterFar"
fm = far_mat.node_tree.nodes[mp.name]
fm.inputs["Scale"].default_value = (1 / OCEAN_SCALE,) * 3
far.data.materials.append(far_mat)

# ---------------------------------------------------------------- sky + sun
world = bpy.data.worlds.new("Sky")
world.use_nodes = True
wt = world.node_tree
for n in list(wt.nodes):
    wt.nodes.remove(n)
wo = N(wt, "ShaderNodeOutputWorld")
bg = N(wt, "ShaderNodeBackground")
sky = N(wt, "ShaderNodeTexSky", sky_type="MULTIPLE_SCATTERING")
sky.sun_disc = True
sky.sun_size = math.radians(0.9)
sky.sun_intensity = 1.0
sky.sun_elevation = math.radians(SUN_ELEV)
sky.sun_rotation = math.radians(SUN_AZ)
sky.air_density = 1.0
sky.aerosol_density = 0.6
sky.ozone_density = 1.0
sky.altitude = 0.0
L(wt, sky.outputs[0], bg.inputs[0])
bg.inputs[1].default_value = 1.0
L(wt, bg.outputs[0], wo.inputs[0])
haze = N(wt, "ShaderNodeVolumeScatter")
haze.inputs["Color"].default_value = (0.75, 0.85, 1.0, 1)
haze.inputs["Density"].default_value = 0.0015
haze.inputs["Anisotropy"].default_value = 0.5
if os.environ.get("HAZE") == "1":
    L(wt, haze.outputs[0], wo.inputs["Volume"])
scn.world = world

# ---------------------------------------------------------------- eruption: plume (volume)
plume_mat = bpy.data.materials.new("Plume")
plume_mat.use_nodes = True
p = plume_mat.node_tree
for n in list(p.nodes):
    p.nodes.remove(n)
pout = N(p, "ShaderNodeOutputMaterial")
pv = N(p, "ShaderNodeVolumePrincipled")
pv.inputs["Color"].default_value = (0.16, 0.14, 0.13, 1)
pv.inputs["Anisotropy"].default_value = 0.3
ptc = N(p, "ShaderNodeTexCoord")
psep = N(p, "ShaderNodeSeparateXYZ")
L(p, ptc.outputs["Object"], psep.inputs[0])
pmap = N(p, "ShaderNodeMapping")
L(p, ptc.outputs["Object"], pmap.inputs[0])
pmap.inputs["Scale"].default_value = (1.0, 1.0, 0.6)
pd = p.driver_add(f'nodes["{pmap.name}"].inputs["Location"].default_value', 2)
pd.driver.expression = "-frame*0.035"
pn = N(p, "ShaderNodeTexNoise", noise_dimensions="3D")
pn.inputs["Scale"].default_value = 2.2
pn.inputs["Detail"].default_value = 7
L(p, pmap.outputs[0], pn.inputs["Vector"])
rad = N(p, "ShaderNodeVectorMath", operation="LENGTH")
pc = N(p, "ShaderNodeCombineXYZ")
L(p, psep.outputs[0], pc.inputs[0])
L(p, psep.outputs[1], pc.inputs[1])
L(p, pc.outputs[0], rad.inputs[0])
zn = maprange(p, psep.outputs[2], -1.0, 1.0)             # 0 bottom -> 1 top
width = math_(p, "ADD", 0.35, math_(p, "MULTIPLY", zn.outputs[0], 0.65))   # widens upward
rad_n = math_(p, "DIVIDE", rad.outputs["Value"], width)
radial = maprange(p, rad_n, 1.0, 0.25)
top_fade = maprange(p, zn.outputs[0], 1.0, 0.55)
shape = math_(p, "MULTIPLY", radial.outputs[0], top_fade.outputs[0])
nclip = maprange(p, pn.outputs["Fac"], 0.35, 0.75)
pstr = val_node(p, 0.0, "plume_amt")
keys_on(pstr, [(1, 0), (40, 0), (70, 0.4), (110, 0.6), (150, 1.0), (225, 1.0), (262, 0.0), (300, 0)])
dens = math_(p, "MULTIPLY", math_(p, "MULTIPLY", shape, nclip.outputs[0]), pstr.outputs[0])
L(p, math_(p, "MULTIPLY", dens, 3.5), pv.inputs["Density"])
glow = math_(p, "MULTIPLY", math_(p, "MULTIPLY", maprange(p, zn.outputs[0], 0.35, 0.0).outputs[0], dens), pstr.outputs[0])
pv.inputs["Emission Color"].default_value = (1.0, 0.28, 0.03, 1)
L(p, math_(p, "MULTIPLY", glow, 8.0), pv.inputs["Emission Strength"])
L(p, pv.outputs[0], pout.inputs["Volume"])

bpy.ops.mesh.primitive_cube_add(size=2, location=(HX, HY, 5.0))
plume = bpy.context.object
plume.name = "Plume"
plume.scale = (6.0, 6.0, 8.0)
plume.data.materials.append(plume_mat)
plume.visible_shadow = False
plume.visible_glossy = False

# ---------------------------------------------------------------- eruption: lava fountain particles
lava_blob_mat = bpy.data.materials.new("LavaBlob")
lava_blob_mat.use_nodes = True
lt = lava_blob_mat.node_tree
for n in list(lt.nodes):
    lt.nodes.remove(n)
lo = N(lt, "ShaderNodeOutputMaterial")
le = N(lt, "ShaderNodeEmission")
le.inputs["Color"].default_value = (1.0, 0.33, 0.04, 1)
le.inputs["Strength"].default_value = 30.0
L(lt, le.outputs[0], lo.inputs["Surface"])
bpy.ops.mesh.primitive_ico_sphere_add(radius=0.3, subdivisions=1, location=(0, 0, -50))
blob = bpy.context.object
blob.name = "LavaBlob"
blob.data.materials.append(lava_blob_mat)
bpy.ops.mesh.primitive_ico_sphere_add(radius=0.3, subdivisions=2, location=(HX, HY, 3.0))
emitter = bpy.context.object
emitter.name = "CraterEmitter"
emitter.hide_render = False
emitter.visible_camera = False
emitter.visible_shadow = False
emitter.show_instancer_for_render = False
ps_mod = emitter.modifiers.new("Fountain", "PARTICLE_SYSTEM")
ps = ps_mod.particle_system.settings
ps.count = 9000
ps.frame_start = 118
ps.frame_end = 236
ps.lifetime = 52
ps.lifetime_random = 0.4
ps.emit_from = "VERT"
ps.normal_factor = 2.5
ps.object_align_factor = (0.0, 0.0, 8.5)
ps.factor_random = 3.0
ps.object_factor = 0.0
ps.render_type = "OBJECT"
ps.instance_object = blob
ps.particle_size = 1.0
ps.size_random = 0.7
ps.effector_weights.gravity = 0.38
ps.use_dynamic_rotation = False
ps.physics_type = "NEWTON"
ps.timestep = 0.04

# animate emitter + plume to ride on the growing summit
for f in range(1, F_END + 1, 4):
    z = summit_z(f)
    emitter.location = (HX, HY, z + 0.15)
    emitter.keyframe_insert("location", frame=f)
    plume.location = (HX, HY, z + plume.scale[2] * 0.7)
    plume.keyframe_insert("location", frame=f)
scn.frame_set(1)

# ---------------------------------------------------------------- camera
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 20
cam_data.clip_start = 0.3
cam_data.clip_end = 400000
cam = bpy.data.objects.new("Camera", cam_data)
scn.collection.objects.link(cam)
scn.camera = cam
target = bpy.data.objects.new("CamTarget", None)
scn.collection.objects.link(target)
tc_ = cam.constraints.new("TRACK_TO")
tc_.target = target
tc_.track_axis = "TRACK_NEGATIVE_Z"
tc_.up_axis = "UP_Y"
for f, loc, tgt in [
    (1,   (-30, -80, 11.0), (-2, 4, 0.0)),
    (110, (-20, -68, 12.0), (-1, 3, 0.8)),
    (230, (-2,  -52, 14.0), (0, 2, 2.2)),
    (300, (4,   -46, 15.0), (0, 2, 1.8)),
]:
    cam.location = loc
    cam.keyframe_insert("location", frame=f)
    target.location = tgt
    target.keyframe_insert("location", frame=f)

# ---------------------------------------------------------------- captions
FONT = r"C:\Windows\Fonts\malgunbd.ttf"
fnt = bpy.data.fonts.load(FONT) if os.path.exists(FONT) else None
CAPS = [
    ("제주도의 탄생", "화산이 만든 섬", 1, 70),
    ("약 180만 년 전", "얕은 바다 밑에서 시작된 화산 분출", 80, 150),
    ("해수면 위로 솟아오른 화산섬", "분출이 거듭되며 용암이 쌓인다", 155, 215),
    ("한라산의 형성", "용암 분출과 화산재, 섬의 중심이 솟는다", 150, 235),
    ("푸르른 제주도", "화산활동이 잦아들고 식물이 자란다", 240, 300),
]
CAPS = [CAPS[0], CAPS[1], CAPS[2], CAPS[4]]
CAPS = [
    ("제주도의 탄생", "화산이 만든 섬", 1, 66),
    ("약 180만 년 전 · 해저 화산 분출", "얕은 바다 밑에서 용암이 솟는다", 70, 128),
    ("해수면 위로 솟은 화산섬", "분출이 거듭되며 용암이 쌓인다", 132, 190),
    ("한라산의 형성", "용암과 화산재가 섬의 중심을 높인다", 194, 240),
    ("푸르른 제주도", "화산활동이 잦아들고 식물이 자란다", 246, 300),
]


def make_text(body, size, y, mat_strength_keys):
    cu = bpy.data.curves.new("txt", "FONT")
    cu.body = body
    cu.size = size
    cu.align_x = "CENTER"
    if fnt:
        cu.font = fnt
    ob = bpy.data.objects.new("Caption", cu)
    scn.collection.objects.link(ob)
    ob.parent = cam
    ob.location = (0, y, -9.0)
    for a in ("visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter", "visible_shadow"):
        setattr(ob, a, False)
    m = bpy.data.materials.new("capmat")
    m.use_nodes = True
    tt = m.node_tree
    for n in list(tt.nodes):
        tt.nodes.remove(n)
    o = N(tt, "ShaderNodeOutputMaterial")
    e = N(tt, "ShaderNodeEmission")
    e.inputs["Color"].default_value = (1.0, 0.97, 0.9, 1)
    e.inputs["Strength"].default_value = 6.0
    tr = N(tt, "ShaderNodeBsdfTransparent")
    mx = N(tt, "ShaderNodeMixShader")
    L(tt, tr.outputs[0], mx.inputs[1])
    L(tt, e.outputs[0], mx.inputs[2])
    L(tt, mx.outputs[0], o.inputs["Surface"])
    for f, s in mat_strength_keys:
        mx.inputs[0].default_value = s / 3.0
        mx.inputs[0].keyframe_insert("default_value", frame=f)
    cu.materials.append(m)
    return ob


for title, sub, a, b in CAPS:
    fade = 10
    ks = [(max(1, a - fade), 0.0), (a, 3.0), (b - 4, 3.0), (b + fade, 0.0)]
    big = 0.62 if a == 1 else 0.40
    make_text(title, big, -2.45 if a != 1 else -1.7, ks)
    make_text(sub, 0.24, -3.1 if a != 1 else -2.5, ks)

# ---------------------------------------------------------------- render settings
r = scn.render
r.engine = "CYCLES"
r.resolution_x, r.resolution_y = 1920, 1080
r.resolution_percentage = 100
r.image_settings.file_format = "PNG"
r.film_transparent = False
cy = scn.cycles
cy.samples = 96
cy.use_denoising = True
cy.adaptive_threshold = 0.02
cy.max_bounces = 8
cy.transmission_bounces = 8
cy.glossy_bounces = 6
cy.volume_bounces = 1
cy.volume_step_rate = 2.0
cy.volume_max_steps = 256
cy.sample_clamp_indirect = 10
try:
    cprefs = bpy.context.preferences.addons["cycles"].preferences
    for dt in ("OPTIX", "CUDA"):
        try:
            cprefs.compute_device_type = dt
            cprefs.get_devices()
            devs = [d for d in cprefs.devices if d.type == dt]
            if devs:
                for d in cprefs.devices:
                    d.use = d.type == dt
                cy.device = "GPU"
                print("render device", dt, [d.name for d in devs])
                break
        except Exception as e:
            print("device", dt, e)
except Exception as e:
    print("GPU setup failed", e)

vs = scn.view_settings
vs.view_transform = "AgX"
try:
    vs.look = "AgX - Medium High Contrast"
except Exception:
    pass
vs.exposure = -2.5
print("SUN_DIR", tuple(sky.sun_direction))

# compositor glow (lava + sun)
try:
    ng = bpy.data.node_groups.new("Comp", "CompositorNodeTree")
    scn.compositing_node_group = ng
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    gl = ng.nodes.new("CompositorNodeGlare")
    go = ng.nodes.new("NodeGroupOutput")
    gl.inputs["Type"].default_value = "Bloom"
    gl.inputs["Highlights Threshold"].default_value = 6.0
    gl.inputs["Strength"].default_value = 0.2
    gl.inputs["Size"].default_value = 0.35
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
    ng.links.new(gl.outputs["Image"], go.inputs[0])
    print("compositor glare set; glare inputs:", [i.name for i in gl.inputs])
except Exception as e:
    print("compositor setup failed:", e)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "jeju_birth.blend"))
print("saved")
