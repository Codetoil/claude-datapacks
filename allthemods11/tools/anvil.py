"""Minimal reader for Minecraft region (.mca) files and NBT, standard library only."""
import gzip
import struct
import zlib
from pathlib import Path


class _Reader:
    __slots__ = ("b", "i")

    def __init__(self, b):
        self.b, self.i = b, 0

    def take(self, n):
        s = self.b[self.i:self.i + n]
        self.i += n
        return s

    def unpack(self, fmt):
        size = struct.calcsize(fmt)
        v = struct.unpack_from(fmt, self.b, self.i)
        self.i += size
        return v[0] if len(v) == 1 else v

    def string(self):
        n = self.unpack(">H")
        return self.take(n).decode("utf-8", "replace")


def _payload(r, tag):
    if tag == 1: return r.unpack(">b")
    if tag == 2: return r.unpack(">h")
    if tag == 3: return r.unpack(">i")
    if tag == 4: return r.unpack(">q")
    if tag == 5: return r.unpack(">f")
    if tag == 6: return r.unpack(">d")
    if tag == 7:
        n = r.unpack(">i")
        return r.take(n)
    if tag == 8: return r.string()
    if tag == 9:
        sub, n = r.unpack(">bi")
        return [_payload(r, sub) for _ in range(n)]
    if tag == 10:
        out = {}
        while True:
            t = r.unpack(">b")
            if t == 0:
                return out
            name = r.string()
            out[name] = _payload(r, t)
    if tag == 11:
        n = r.unpack(">i")
        return list(struct.unpack_from(f">{n}i", r.take(4 * n)))
    if tag == 12:
        n = r.unpack(">i")
        return list(struct.unpack_from(f">{n}q", r.take(8 * n)))
    raise ValueError(f"bad NBT tag {tag}")


def parse_nbt(data):
    r = _Reader(data)
    tag = r.unpack(">b")
    r.string()
    return _payload(r, tag)


def read_region(path):
    """Yield (local_x, local_z, chunk_nbt) for every chunk stored in a region file."""
    data = Path(path).read_bytes()
    if len(data) < 8192:
        return
    for idx in range(1024):
        loc = struct.unpack_from(">I", data, idx * 4)[0]
        off, count = loc >> 8, loc & 0xFF
        if off == 0 or count == 0:
            continue
        length, comp = struct.unpack_from(">IB", data, off * 4096)
        raw = data[off * 4096 + 5: off * 4096 + 4 + length]
        if comp == 2:
            raw = zlib.decompress(raw)
        elif comp == 1:
            raw = gzip.decompress(raw)
        elif comp == 3:
            pass
        else:
            continue  # lz4 / external chunk files: not needed here
        yield idx % 32, idx // 32, parse_nbt(raw)


def unpack_longs(longs, bits, count):
    """Unpack a 'no spanning' packed long array (1.16+ format) into `count` ints."""
    per = 64 // bits
    mask = (1 << bits) - 1
    out = []
    for word in longs:
        word &= (1 << 64) - 1
        for k in range(per):
            out.append((word >> (k * bits)) & mask)
            if len(out) == count:
                return out
    return out
