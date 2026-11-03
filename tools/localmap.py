"""Renders painted local maps from Nehrim's data files, without the game, using the engine's camera and map shader."""
import time
time.clock = time.perf_counter

import hashlib, io, json, multiprocessing, pickle, struct, sys, zlib
from pathlib import Path

import moderngl
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import bsa
import tes4

ROOT = Path(__file__).parent.parent
CACHE = ROOT / 'research' / 'localmap_cache'
OUT = ROOT / 'docs' / 'img' / 'local'

UNITS_PER_PX = 17.0  # 4352 unit frustum on a 256 px target
MAX_ZOOM = 8
FRAME_MARGIN = 1.15
SECRET_PANEL = r'textures\effects\secretblack.dds'  # up-facing panels that blank secret rooms on the map; a guide needs them visible
NEAR = 100.0
CAMERA_LIFT = 20000.0
PAPER_CLEAR = (0.9019, 0.8314, 0.72166, 1.0)
INK = np.array([0.459, 0.231, 0.129])
MODEL_TYPES = {'STAT', 'ACTI', 'DOOR', 'CONT', 'FURN', 'LIGH', 'MISC', 'WEAP', 'ARMO', 'BOOK', 'ALCH',
               'APPA', 'CLOT', 'FLOR', 'INGR', 'KEYM', 'SGST', 'SLGM', 'AMMO', 'SBSP'}


class Assets:
    def __init__(self):
        self.files = {}
        for p in sorted(bsa.DATA.glob('*.bsa')):
            for name, size, off, comp in bsa.entries(p):
                self.files.setdefault(name.lower(), (p, size, off, comp))

    def read(self, name):
        hit = self.files.get(name.lower().replace('/', '\\'))
        if not hit:
            return None
        p, size, off, comp = hit
        with open(p, 'rb') as f:
            f.seek(off)
            blob = f.read(size)
        return zlib.decompress(blob[4:]) if comp else blob


def land_layers(rec):
    layers, current = [], None
    for t, v in rec.subs():
        if t == 'BTXT':
            fid, quad = struct.unpack('<IB', v[:5])
            layers.append(dict(fid=fid, quad=quad, layer=-1, alpha=None))
        elif t == 'ATXT':
            fid, quad, _, layer = struct.unpack('<IBBH', v[:8])
            current = dict(fid=fid, quad=quad, layer=layer, alpha=np.zeros((17, 17), 'f4'))
            layers.append(current)
        elif t == 'VTXT' and current is not None:
            for i in range(len(v) // 8):
                pos, _, op = struct.unpack_from('<HHf', v, i * 8)
                if pos < 289:
                    current['alpha'][pos // 17, pos % 17] = op
    return layers


def build_index():
    path = CACHE / 'index.pkl'
    if path.exists():
        return pickle.loads(path.read_bytes())
    CACHE.mkdir(parents=True, exist_ok=True)
    records = tes4.load('Nehrim.esm')
    overrides = {r.fid: r for r in tes4.load('Translation.esp') if r.type in MODEL_TYPES or r.type == 'LTEX'}
    models, north_bases, ltex, grids = {}, set(), {}, {}
    for r in records:
        if r.type == 'CELL':
            xclc = r.sub('XCLC')
            if xclc:
                grids[r.fid] = struct.unpack('<ii', xclc[:8])
        elif r.type == 'LTEX':
            icon = overrides.get(r.fid, r).sub('ICON')
            if icon:
                ltex[r.fid] = tes4.zs(icon)
        elif r.type in MODEL_TYPES:
            r = overrides.get(r.fid, r)
            if r.edid == 'NorthMarker':
                north_bases.add(r.fid)
            if 'marker' in r.edid.lower():
                continue
            modl = r.sub('MODL')
            if modl:
                models[r.fid] = tes4.zs(modl)
    interiors, exteriors, land, by_ref, north = {}, {}, {}, {}, {}
    for r in records:
        if r.type not in ('REFR', 'ACHR', 'ACRE', 'LAND'):
            continue
        cell = wrld = None
        for gtype, label in r.path:
            lid = struct.unpack('<I', label)[0]
            if gtype == 1:
                wrld = lid
            if gtype in (6, 8, 9, 10):
                cell = lid
        if r.type == 'LAND':
            if wrld is not None and cell in grids:
                land[(wrld, *grids[cell])] = dict(VHGT=r.sub('VHGT'), VNML=r.sub('VNML'), VCLR=r.sub('VCLR'),
                                                  layers=land_layers(r))
            continue
        data = r.sub('DATA')
        name = r.sub('NAME')
        if not data or not name:
            continue
        base = struct.unpack('<I', name)[0]
        pos = struct.unpack('<6f', data)
        by_ref[r.fid] = (wrld, cell, pos)
        if r.type != 'REFR' or r.flags & 0x20:
            continue
        if base in north_bases and wrld is None:
            north[cell] = pos[5]
        if r.flags & 0x800 or base not in models:
            continue
        scale = r.sub('XSCL')
        ref = (base, pos, struct.unpack('<f', scale)[0] if scale else 1.0)
        if wrld is None:
            interiors.setdefault(cell, []).append(ref)
        else:
            exteriors.setdefault((wrld, int(pos[0] // 4096), int(pos[1] // 4096)), []).append(ref)
    parents = {r.fid: struct.unpack('<I', r.sub('WNAM'))[0] for r in records if r.type == 'WRLD' and r.sub('WNAM')}
    index = dict(models=models, ltex=ltex, interiors=interiors, exteriors=exteriors,
                 land=land, by_ref=by_ref, north=north, parents=parents)
    path.write_bytes(pickle.dumps(index, protocol=4))
    return index


def geometry(block, m, NifFormat):
    d = block.data
    tris = list(d.get_triangles())
    if not d.num_vertices or not tris:
        return None
    v = np.array([(p.x, p.y, p.z) for p in d.vertices], 'f4')
    has_n = d.has_normals and len(d.normals) == len(v)
    n = np.array([(p.x, p.y, p.z) for p in d.normals], 'f4') if has_n else None
    uv = np.zeros((len(v), 2), 'f4')
    if len(d.uv_sets) and len(d.uv_sets[0]) == len(v):
        uv = np.array([(t.u, t.v) for t in d.uv_sets[0]], 'f4')
    col = np.ones((len(v), 3), 'f4')
    if d.has_vertex_colors and len(d.vertex_colors) == len(v):
        col = np.array([(c.r, c.g, c.b) for c in d.vertex_colors], 'f4')
    tex, blend, test, threshold, two_sided = None, False, False, 0, False
    for prop in block.properties:
        if isinstance(prop, NifFormat.NiTexturingProperty) and prop.has_base_texture and prop.base_texture.source:
            tex = prop.base_texture.source.file_name.decode('latin1')
        elif isinstance(prop, NifFormat.NiAlphaProperty):
            blend, test, threshold = bool(prop.flags & 1), bool(prop.flags & 0x200), prop.threshold
        elif isinstance(prop, NifFormat.NiStencilProperty):
            two_sided = (prop.flags >> 10) & 3 == 3
    rot = m[:3, :3].astype('f4')
    v = v @ rot + m[3, :3].astype('f4')
    if n is None:
        n = np.zeros_like(v)
        n[:, 2] = 1
    else:
        n = n @ rot
    return dict(v=v, n=n, uv=uv, col=col, i=np.array(tris, 'u4'), tex=tex, blend=blend,
                test=test, threshold=threshold, two_sided=two_sided)


def parse_nif(blob):
    from pyffi.formats.nif import NifFormat
    data = NifFormat.Data()
    data.read(io.BytesIO(blob))
    parts = []

    def walk(block, parent):
        if not isinstance(block, NifFormat.NiAVObject):
            return
        name = block.name.decode('latin1').lower() if block.name else ''
        if block.flags & 1 or 'editormarker' in name or 'collisionmarker' in name:
            return
        m = np.array(block.get_transform().as_list(), 'f8') @ parent
        if isinstance(block, NifFormat.NiNode):
            for child in block.children:
                if child:
                    walk(child, m)
        elif isinstance(block, (NifFormat.NiTriShape, NifFormat.NiTriStrips)) and block.data:
            part = geometry(block, m, NifFormat)
            if part:
                parts.append(part)

    for root in data.roots:
        walk(root, np.eye(4))
    return parts


def mesh_cache_path(name):
    return CACHE / 'mesh' / (hashlib.sha1(name.lower().encode()).hexdigest() + '.pkl')


_worker_assets = None


def parse_mesh_job(name):
    global _worker_assets
    if _worker_assets is None:
        _worker_assets = Assets()
    path = mesh_cache_path(name)
    if path.exists():
        return
    blob = _worker_assets.read('meshes\\' + name)
    try:
        parts = parse_nif(blob) if blob else []
    except Exception as e:
        print('nif failed', name, repr(e)[:100], flush=True)
        parts = []
    path.write_bytes(pickle.dumps(parts, protocol=4))


def prebuild_meshes(names):
    (CACHE / 'mesh').mkdir(parents=True, exist_ok=True)
    todo = sorted({n for n in names if not mesh_cache_path(n).exists()})
    if todo:
        print(f'parsing {len(todo)} meshes', flush=True)
        with multiprocessing.Pool(max(2, multiprocessing.cpu_count() - 2)) as pool:
            for _ in pool.imap_unordered(parse_mesh_job, todo, chunksize=8):
                pass


def euler(rx, ry, rz):
    cx, sx, cy, sy, cz, sz = np.cos(rx), np.sin(rx), np.cos(ry), np.sin(ry), np.cos(rz), np.sin(rz)
    rot_x = np.array([[1, 0, 0], [0, cx, sx], [0, -sx, cx]])
    rot_y = np.array([[cy, 0, -sy], [0, 1, 0], [sy, 0, cy]])
    rot_z = np.array([[cz, sz, 0], [-sz, cz, 0], [0, 0, 1]])
    return rot_z @ rot_y @ rot_x  # column vectors; game angles run clockwise


def land_mesh(rec, gx, gy):
    raw = rec.get('VHGT')
    if not raw:
        return None
    offset = struct.unpack('<f', raw[:4])[0]
    deltas = np.frombuffer(raw[4:4 + 1089], 'i1').reshape(33, 33).astype('f8')
    h = np.zeros((33, 33))
    row = offset
    for r in range(33):
        row += deltas[r, 0]
        h[r, 0] = row
        h[r, 1:] = row + np.cumsum(deltas[r, 1:])
    h *= 8
    xs, ys = np.meshgrid(np.arange(33) * 128.0 + gx * 4096, np.arange(33) * 128.0 + gy * 4096)
    v = np.stack([xs, ys, h], -1).reshape(-1, 3).astype('f4')
    raw_n = rec.get('VNML')
    if raw_n and len(raw_n) >= 3267:
        n = np.frombuffer(raw_n[:3267], 'i1').reshape(-1, 3).astype('f4') / 127
    else:
        n = np.tile(np.array([0, 0, 1], 'f4'), (1089, 1))
    u, w = np.meshgrid(np.arange(33) / 32, np.arange(33) / 32)
    uv = np.stack([u, w], -1).reshape(-1, 2).astype('f4')
    ids = []
    for r in range(32):
        for c in range(32):
            a, b, d, e = r * 33 + c, r * 33 + c + 1, (r + 1) * 33 + c, (r + 1) * 33 + c + 1
            ids += [a, b, e, a, e, d]
    return dict(v=v, n=n, uv=uv, col=np.ones_like(v), i=np.array(ids, 'u4').reshape(-1, 3), h=h)


def land_color(rec, ctx):
    S = 128
    img = np.zeros((S * 2, S * 2, 3), 'f4')
    for quad in range(4):
        y0, x0 = (quad >> 1) * S, (quad & 1) * S
        layers = sorted((l for l in rec['layers'] if l['quad'] == quad), key=lambda l: l['layer'])
        tile = np.full((S, S, 3), 0.55, 'f4')
        for l in layers:
            tex = ctx.land_tile(l['fid'])
            if l['alpha'] is None:
                tile = tex.copy()
            else:
                alpha = np.asarray(Image.fromarray(l['alpha']).resize((S, S), Image.BILINEAR))[..., None]
                tile = tile * (1 - alpha) + tex * alpha
        img[y0:y0 + S, x0:x0 + S] = tile
    if rec.get('VCLR') and len(rec['VCLR']) >= 3267:
        vc = np.frombuffer(rec['VCLR'][:3267], 'u1').reshape(33, 33, 3)
        vc = np.asarray(Image.fromarray(vc, 'RGB').resize((S * 2, S * 2), Image.BILINEAR), 'f4') / 255
        img *= vc
    return (np.clip(img, 0, 1) * 255).astype('u1')


VERT = """#version 330
uniform vec4 frame; uniform vec2 depth;
in vec3 p; in vec3 n; in vec2 uv; in vec3 c;
out vec3 vn; out vec2 vuv; out vec3 vc; out float z01;
void main(){
  z01 = (depth.x - p.z - 100.0) / (depth.y - 100.0);
  gl_Position = vec4((p.x - frame.x) / frame.z, (p.y - frame.y) / frame.w, z01 * 2.0 - 1.0, 1.0);
  vn = n; vuv = uv; vc = c;
}"""
FRAG_COLOR = """#version 330
uniform sampler2D base; uniform float threshold;
in vec3 vn; in vec2 vuv; in vec3 vc; out vec4 o;
void main(){
  vec4 t = texture(base, vuv);
  if (t.a < threshold) discard;
  float lit = 0.6 + 0.4 * max(normalize(vn).z, 0.0);
  o = vec4(t.rgb * vc * lit, t.a);
}"""
# SLS2073.pso and SLS2068.vso: rgb = encoded normal, a = 5*z - 4.4.
FRAG_NORMAL = """#version 330
uniform sampler2D base; uniform float threshold;
in vec3 vn; in vec2 vuv; in float z01; out vec4 o;
void main(){
  if (threshold > 0.0 && texture(base, vuv).a < threshold) discard;
  o = vec4(normalize(vn) * 0.5 + 0.5, clamp(z01 * 5.0 - 4.4, 0.0, 1.0));
}"""


def map_shader(src0, src1, paper, size):
    """MAP000.pso: 3x3 Sobel on the normal and depth pass, inked over paper plus a quarter of the colour pass."""
    w, h = size
    pad = np.pad(src0, ((1, 1), (1, 1), (0, 0)), mode='edge')
    at = lambda dx, dy: pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
    gy = 2 * at(0, -1) + at(-1, -1) + at(1, -1) - at(-1, 1) - 2 * at(0, 1) - at(1, 1)
    gx = 2 * at(-1, 0) + at(-1, -1) + at(-1, 1) - at(1, -1) - 2 * at(1, 0) - at(1, 1)
    edge = gx * gx + gy * gy
    ink = edge[..., :3] @ np.array([0.2, 0.2, 0.15]) + np.minimum(edge[..., 3] * 10, 0.1)
    ink = np.minimum(ink, 0.5)[..., None]
    tiled = np.tile(paper, (h // paper.shape[0] + 1, w // paper.shape[1] + 1, 1))[:h, :w]
    base = tiled * 0.75 + src1[..., :3] * 0.25
    return np.clip(base * (1 - ink) + INK * ink, 0, 1)


class Renderer:
    def __init__(self, index):
        self.index = index
        self.assets = Assets()
        self.gl = moderngl.create_standalone_context()
        self.color = self.gl.program(vertex_shader=VERT, fragment_shader=FRAG_COLOR)
        self.normal = self.gl.program(vertex_shader=VERT, fragment_shader=FRAG_NORMAL)
        self.textures = {}
        self.tiles = {}
        self.meshes = {}
        self.white = self.gl.texture((1, 1), 4, b'\xff\xff\xff\xff')
        blob = self.assets.read('textures\\menus\\map\\local\\mappaper01.dds')
        self.paper = np.asarray(Image.open(io.BytesIO(blob)).convert('RGB'), 'f8') / 255

    def mesh(self, name):
        key = name.lower()
        if key not in self.meshes:
            parse_mesh_job(name)
            parts = pickle.loads(mesh_cache_path(name).read_bytes())
            self.meshes[key] = [p for p in parts if (p['tex'] or '').lower() != SECRET_PANEL]
        return self.meshes[key]

    def image(self, name):
        name = name.lower().replace('/', '\\')
        if not name.startswith('textures\\'):
            name = 'textures\\' + name
        blob = self.assets.read(name)
        if not blob:
            return None
        try:
            im = Image.open(io.BytesIO(blob)).convert('RGBA')
        except Exception:
            return None
        im.thumbnail((256, 256))
        return im

    def texture(self, name):
        if not name:
            return self.white
        key = name.lower()
        if key not in self.textures:
            im = self.image(name)
            if im is None:
                self.textures[key] = self.white
            else:
                tex = self.gl.texture(im.size, 4, im.tobytes())
                tex.build_mipmaps()
                tex.repeat_x = tex.repeat_y = True
                self.textures[key] = tex
        return self.textures[key]

    def land_tile(self, fid):
        if fid not in self.tiles:
            icon = self.index['ltex'].get(fid)
            im = self.image('landscape\\' + icon) if icon else None
            arr = np.full((128, 128, 3), 0.55, 'f4')
            if im is not None:
                arr = np.asarray(im.convert('RGB').resize((64, 64), Image.BILINEAR), 'f4') / 255
                arr = np.tile(arr, (2, 2, 1))
            self.tiles[fid] = arr
        return self.tiles[fid]

    def gather(self, refs, view):
        groups = {}
        for base, pos, scale in refs:
            name = self.index['models'].get(base)
            if not name or name.lower().endswith('.spt'):
                continue
            rot = euler(pos[3], pos[4], pos[5])
            for part in self.mesh(name):
                vw = (part['v'] * scale) @ rot.T + np.array(pos[:3])
                nw = part['n'] @ rot.T
                threshold = (part['threshold'] + 1) / 256 if part['test'] else 0.0
                key = (part['tex'], part['blend'], threshold, part['two_sided'])
                groups.setdefault(key, []).append((vw @ view.T, nw @ view.T, part['uv'], part['col'], part['i']))
        return groups

    def buffers(self, items):
        arrays, indices, offset = [], [], 0
        for v, n, uv, col, tris in items:
            arrays.append(np.hstack([v, n, uv, col]).astype('f4'))
            indices.append(tris.astype('u4') + offset)
            offset += len(v)
        return self.gl.buffer(np.vstack(arrays).tobytes()), self.gl.buffer(np.vstack(indices).tobytes())

    def render(self, refs, center, size, zrange, lands=(), view=np.eye(3), upp=UNITS_PER_PX):
        groups = self.gather(refs, view)
        cx, cy = center
        cam_z = zrange[1] + CAMERA_LIFT
        far = cam_z - zrange[0] + 10
        frame = (cx, cy, size[0] * upp / 2, size[1] * upp / 2)
        draws = [(self.texture(k[0]), k[1], k[2], k[3], items) for k, items in groups.items()]
        draws += [(tex, False, 0.0, False, [(p['v'] @ view.T, p['n'] @ view.T, p['uv'], p['col'], p['i'])])
                  for p, tex in lands]
        draws.sort(key=lambda d: d[1])

        passes = []
        for program, is_color in ((self.color, True), (self.normal, False)):
            fbo = self.gl.simple_framebuffer(size, components=4, dtype='f1')
            fbo.use()
            fbo.clear(*PAPER_CLEAR, depth=1.0)
            self.gl.enable(moderngl.DEPTH_TEST)
            program['frame'] = frame
            program['depth'] = (cam_z, far)
            for tex, blend, threshold, two_sided, items in draws:
                if blend and not is_color:
                    continue
                (self.gl.disable if two_sided else self.gl.enable)(moderngl.CULL_FACE)
                (self.gl.enable if blend else self.gl.disable)(moderngl.BLEND)
                self.gl.depth_mask = not blend
                vbo, ibo = self.buffers(items)
                keep = [a for a in ('p', 'n', 'uv', 'c') if a in program]
                vao = self.gl.vertex_array(program, [(vbo, packed_format(keep), *keep)], ibo)
                tex.use(0)
                program['threshold'] = threshold
                vao.render(moderngl.TRIANGLES)
                vao.release(); vbo.release(); ibo.release()
            self.gl.depth_mask = True
            arr = np.frombuffer(fbo.read(components=4, dtype='f1'), 'u1').reshape(size[1], size[0], 4)
            passes.append(arr[::-1].astype('f8') / 255)
            fbo.release()
        return map_shader(passes[1], passes[0], self.paper, size)


def packed_format(keep):
    sizes = dict(p=(3, 12), n=(3, 12), uv=(2, 8), c=(3, 12))
    return ' '.join(f'{sizes[a][0]}f' if a in keep else f'{sizes[a][1]}x' for a in ('p', 'n', 'uv', 'c'))


def north_view(angle):
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])  # takes the north marker's heading to screen up


def interior_frame(r, refs, view, item, size):
    """Fits the cell to the image, zooming small ones, and keeps the item well inside the frame."""
    lows, highs = [], []
    for base, pos, scale in refs:
        name = r.index['models'].get(base)
        rot = euler(pos[3], pos[4], pos[5])
        for part in r.mesh(name) if name else []:
            v = ((part['v'] * scale) @ rot.T + np.array(pos[:3])) @ view.T
            lows.append(v[:, :2].min(0))
            highs.append(v[:, :2].max(0))
    if not lows:
        return tuple(item), UNITS_PER_PX
    low = np.minimum(np.percentile(lows, 1, axis=0), item)  # percentiles drop stray objects far from the rooms
    high = np.maximum(np.percentile(highs, 99, axis=0), item)
    side = (high - low).max() * FRAME_MARGIN
    upp = float(np.clip(side / max(size), UNITS_PER_PX / MAX_ZOOM, UNITS_PER_PX))
    reach = np.array(size) * upp * 0.38
    center = np.clip((low + high) / 2, np.array(item) - reach, np.array(item) + reach)
    return (float(center[0]), float(center[1])), upp


def draw_pin(rgb, x, y):
    S, R = 4, 8
    im = Image.fromarray((rgb * 255 + 0.5).astype('u1'), 'RGB')
    stamp = Image.new('RGBA', ((R * 2 + 2) * S,) * 2, (0, 0, 0, 0))
    d = ImageDraw.Draw(stamp)
    mid = (R + 1) * S
    d.ellipse([mid - R * S, mid - R * S, mid + R * S, mid + R * S], fill=(255, 255, 255, 255))
    d.ellipse([mid - (R - 2) * S, mid - (R - 2) * S, mid + (R - 2) * S, mid + (R - 2) * S], fill=(200, 40, 30, 255))
    stamp = stamp.resize((R * 2 + 2,) * 2, Image.LANCZOS)
    im.paste(stamp, (round(x) - R - 1, round(y) - R - 1), stamp)
    return im


def interior_scene(r, cell):
    refs = r.index['interiors'].get(cell, [])
    low, high = [], []
    for base, pos, scale in refs:
        name = r.index['models'].get(base)
        for part in r.mesh(name) if name else []:
            low.append(part['v'].min(0) * scale + pos[:3])
            high.append(part['v'].max(0) * scale + pos[:3])
    if not low:
        return refs, (0.0, 1.0)
    low, high = np.min(low, 0), np.max(high, 0)
    mid, radius = (low + high) / 2, np.linalg.norm(high - low) / 2
    return refs, (float(mid[2] - radius), float(mid[2] + radius))  # engine uses the cell node's bounding sphere


def exterior_scene(r, wrld, x, y, size):
    half = max(size) * UNITS_PER_PX / 2
    g0x, g1x = int((x - half) // 4096), int((x + half) // 4096)
    g0y, g1y = int((y - half) // 4096), int((y + half) // 4096)
    refs, lands, zrange = [], [], None
    for gx in range(g0x - 1, g1x + 2):
        for gy in range(g0y - 1, g1y + 2):
            refs += r.index['exteriors'].get((wrld, gx, gy), [])
    for gx in range(g0x, g1x + 1):
        for gy in range(g0y, g1y + 1):
            rec = r.index['land'].get((wrld, gx, gy)) or r.index['land'].get((r.index['parents'].get(wrld), gx, gy))
            part = land_mesh(rec, gx, gy) if rec else None
            if part is None:
                continue
            tex_img = land_color(rec, r)
            tex = r.gl.texture((tex_img.shape[1], tex_img.shape[0]), 3, tex_img.tobytes())
            tex.build_mipmaps()
            lands.append((part, tex))
            low, high = float(part['h'].min()), float(part['h'].max())
            zrange = (min(zrange[0], low), max(zrange[1], high)) if zrange else (low, high)
    return refs, lands, zrange or (0.0, 1.0)


def render_ref(r, ref, size=(384, 384)):
    wrld, cell, pos = r.index['by_ref'][ref]
    x, y = pos[0], pos[1]
    if wrld is None:
        refs, zrange = interior_scene(r, cell)
        view = north_view(r.index['north'].get(cell, 0.0))
        item = (view @ np.array([x, y, 0]))[:2]
        center, upp = interior_frame(r, refs, view, item, size)
        rgb = r.render(refs, center, size, zrange, view=view, upp=upp)
        return draw_pin(rgb, size[0] / 2 + (item[0] - center[0]) / upp, size[1] / 2 - (item[1] - center[1]) / upp)
    refs, lands, zrange = exterior_scene(r, wrld, x, y, size)
    rgb = r.render(refs, (x, y), size, zrange, lands=lands)
    for _, tex in lands:
        tex.release()
    return draw_pin(rgb, size[0] / 2, size[1] / 2)


def wanted_meshes(index, refs_needed):
    names = set()
    for ref in refs_needed:
        hit = index['by_ref'].get(ref)
        if not hit:
            continue
        wrld, cell, pos = hit
        if wrld is None:
            refs = index['interiors'].get(cell, [])
        else:
            gx, gy = int(pos[0] // 4096), int(pos[1] // 4096)
            refs = [q for dx in range(-3, 4) for dy in range(-3, 4)
                    for q in index['exteriors'].get((wrld, gx + dx, gy + dy), [])]
        names |= {index['models'][q[0]] for q in refs if q[0] in index['models']
                  and not index['models'][q[0]].lower().endswith('.spt')}
    return names


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--out', default=str(OUT))
    args = ap.parse_args()
    items = json.loads((ROOT / 'docs' / 'data' / 'collectibles.json').read_text(encoding='utf8'))['items']
    if args.only:
        items = [i for i in items if i['id'] in args.only]
    index = build_index()
    position = lambda i: i['ref'] or i.get('holder')  # carried items sit where their holder is placed
    prebuild_meshes(wanted_meshes(index, [position(i) for i in items]))
    r = Renderer(index)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    missing = []
    for n, item in enumerate(items):
        if position(item) not in index['by_ref']:
            missing.append(item['id'])
            continue
        t = time.time()
        render_ref(r, position(item)).save(out / f"{item['id']}.webp", quality=88, method=6)
        print(n + 1, len(items), item['id'], item.get('cell'), round(time.time() - t, 2), flush=True)
    if missing:
        print('no reference found:', missing)


if __name__ == '__main__':
    main()
