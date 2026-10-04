import struct, zlib

DATA = r"C:\Program Files (x86)\Steam\steamapps\common\Oblivion\Data"


def subrecords(buf):
    i, big = 0, None
    while i < len(buf):
        t = buf[i:i + 4].decode('latin1')
        sz = struct.unpack_from('<H', buf, i + 4)[0]
        i += 6
        if t == 'XXXX':
            big = struct.unpack_from('<I', buf, i)[0]
            i += sz
            continue
        if big is not None:
            sz, big = big, None
        yield t, buf[i:i + sz]
        i += sz


class Rec:
    __slots__ = ('type', 'flags', 'fid', 'data', 'path')

    def subs(self):
        return list(subrecords(self.data))

    def sub(self, t):
        for k, v in subrecords(self.data):
            if k == t:
                return v

    @property
    def edid(self):
        v = self.sub('EDID')
        return v.rstrip(b'\0').decode('latin1') if v else ''


def walk(buf, start=0, end=None, path=()):
    i = start
    end = len(buf) if end is None else end
    while i < end:
        t = buf[i:i + 4].decode('latin1')
        if t == 'GRUP':
            gsz, label, gtype = struct.unpack_from('<I4si', buf, i + 4)
            yield from walk(buf, i + 20, i + gsz, path + ((gtype, label),))
            i += gsz
        else:
            dsz, flags, fid = struct.unpack_from('<III', buf, i + 4)
            d = buf[i + 20:i + 20 + dsz]
            if flags & 0x40000:
                d = zlib.decompress(d[4:])
            r = Rec()
            r.type, r.flags, r.fid, r.data, r.path = t, flags, fid, d, path
            yield r
            i += 20 + dsz


def load(name):
    with open(DATA + '\\' + name, 'rb') as f:
        return list(walk(f.read()))


def zs(b):
    return b.split(b'\0')[0].decode('cp1252', errors='replace') if b else ''
