"""Download AWS Terrain Tiles (terrarium, SRTM-based) around Jeju and resample to a km-spaced grid.
Run:  blender -b -P fetch_dem.py
Outputs: dem/jeju_dem.npy (float32, metres, row 0 = north), dem/jeju_meta.json
"""
import os, io, json, math, urllib.request
import numpy as np
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dem")
TILES = os.path.join(OUT, "tiles")
os.makedirs(TILES, exist_ok=True)

Z = 10
LON0, LON1 = 126.00, 127.10
LAT0, LAT1 = 33.00, 33.70
NX = 640


def merc(lon, lat):
    n = 2 ** Z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - np.log(np.tan(np.radians(lat)) + 1.0 / np.cos(np.radians(lat))) / np.pi) / 2.0 * n
    return x, y


x0, y1 = merc(LON0, LAT0)  # y1 = south (larger)
x1, y0 = merc(LON1, LAT1)  # y0 = north (smaller)
tx0, tx1 = int(math.floor(x0)), int(math.floor(x1))
ty0, ty1 = int(math.floor(y0)), int(math.floor(y1))
print("tiles x", tx0, tx1, "y", ty0, ty1)


def load_tile(tx, ty):
    path = os.path.join(TILES, f"{Z}_{tx}_{ty}.png")
    if not os.path.exists(path):
        url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{tx}/{ty}.png"
        print("GET", url)
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)[::-1]  # Blender stores bottom row first -> flip so row 0 = top
    # terrarium: h = R*256 + G + B/256 - 32768 (values were normalised to 0..1 by Blender; PNG is sRGB-tagged
    # but load as raw via 'Non-Color' to avoid transfer curve)
    return px


# load with Non-Color so values stay linear == raw/255
def load_tile_raw(tx, ty):
    path = os.path.join(TILES, f"{Z}_{tx}_{ty}.png")
    if not os.path.exists(path):
        load_tile(tx, ty)
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1], w, h


mosaic = None
for ty in range(ty0, ty1 + 1):
    row = []
    for tx in range(tx0, tx1 + 1):
        px, w, h = load_tile_raw(tx, ty)
        row.append(px)
    row = np.concatenate(row, axis=1)
    mosaic = row if mosaic is None else np.concatenate([mosaic, row], axis=0)

rgb = mosaic[..., :3] * 255.0
elev = rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0 - 32768.0
print("mosaic", elev.shape, "min/max", elev.min(), elev.max())

# resample to uniform lon/lat grid
km_w = (LON1 - LON0) * 111.32 * math.cos(math.radians((LAT0 + LAT1) / 2))
km_h = (LAT1 - LAT0) * 110.57
NY = int(round(NX * km_h / km_w))
lons = np.linspace(LON0, LON1, NX)
lats = np.linspace(LAT1, LAT0, NY)  # row 0 north
LL, LA = np.meshgrid(lons, lats)
mx, my = merc(LL, LA)
px_ = (mx - tx0) * 256.0 - 0.5
py_ = (my - ty0) * 256.0 - 0.5
ix = np.clip(np.floor(px_).astype(int), 0, elev.shape[1] - 2)
iy = np.clip(np.floor(py_).astype(int), 0, elev.shape[0] - 2)
fx = px_ - ix
fy = py_ - iy
out = (elev[iy, ix] * (1 - fx) * (1 - fy) + elev[iy, ix + 1] * fx * (1 - fy)
       + elev[iy + 1, ix] * (1 - fx) * fy + elev[iy + 1, ix + 1] * fx * fy).astype(np.float32)
np.save(os.path.join(OUT, "jeju_dem.npy"), out)

# Hallasan summit (33.3617N, 126.5292E) in km relative to grid centre
cx, cy = (LON0 + LON1) / 2, (LAT0 + LAT1) / 2
meta = dict(nx=NX, ny=NY, km_w=km_w, km_h=km_h, lon0=LON0, lon1=LON1, lat0=LAT0, lat1=LAT1,
            hallasan_km=[(126.5292 - cx) * 111.32 * math.cos(math.radians(cy)), (33.3617 - cy) * 110.57],
            dem_min=float(out.min()), dem_max=float(out.max()))
json.dump(meta, open(os.path.join(OUT, "jeju_meta.json"), "w"), indent=1)
print(meta)
