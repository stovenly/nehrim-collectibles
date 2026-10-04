"""Minimal Oblivion BSA (v103) reader: list and extract files."""
import struct, sys, zlib
from pathlib import Path

DATA = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Oblivion\Data")


def entries(path):
    with open(path, 'rb') as f:
        magic, ver, off, aflags, nfold, nfile, fnl_dirs, fnl_files, _ = struct.unpack('<4s8I', f.read(36))
        f.seek(off)
        folders = [struct.unpack('<QII', f.read(16)) for _ in range(nfold)]
        recs = []
        for _, cnt, _ in folders:
            dname = f.read(f.read(1)[0])[:-1].decode('latin1')
            for _ in range(cnt):
                _, size, foff = struct.unpack('<QII', f.read(16))
                recs.append((dname, size, foff))
        names = f.read(fnl_files).split(b'\0')
        for (dname, size, foff), n in zip(recs, names):
            compressed = bool(aflags & 4) != bool(size & 0x40000000)
            yield f"{dname}\\{n.decode('latin1')}", size & 0x3FFFFFFF, foff, compressed


def extract(path, want):
    want = want.lower()
    for name, size, foff, comp in entries(path):
        if name.lower() == want:
            with open(path, 'rb') as f:
                f.seek(foff)
                blob = f.read(size)
            return zlib.decompress(blob[4:]) if comp else blob


if __name__ == '__main__':
    if sys.argv[1] == 'ls':
        for p in DATA.glob('*.bsa'):
            for name, *_ in entries(p):
                if sys.argv[2].lower() in name.lower():
                    print(p.name, name)
    elif sys.argv[1] == 'x':
        for p in DATA.glob('*.bsa'):
            b = extract(p, sys.argv[2])
            if b:
                Path(sys.argv[3]).write_bytes(b)
                print('extracted from', p.name, len(b))
                break
