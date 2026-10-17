"""Small strict JSON reader over prepaid ingress; no raw-frame/DTO pre-copy."""

from ..protocol import check


class _Reader:
    def __init__(self, data, start, stop):
        self.data, self.start, self.pos, self.stop = data, start, start, stop
        self.nodes = 0

    def byte(self):
        return -1 if self.pos >= self.stop else self.data[self.pos % len(self.data)]

    def space(self):
        while self.byte() in (9, 32):
            self.pos += 1

    def take(self, expected):
        check(self.byte() == expected, "sync_control_json")
        self.pos += 1

    def node(self):
        self.nodes += 1
        check(self.nodes <= 512, "sync_control_tree")

    def hex4(self):
        value = 0
        for _ in range(4):
            char = self.byte()
            check(48 <= char <= 57 or 65 <= char <= 70 or 97 <= char <= 102, "sync_control_unicode")
            value = value * 16 + (char - 48 if char <= 57 else (char | 32) - 87)
            self.pos += 1
        return value

    def string(self, build):
        self.take(34)
        chars = [] if build else None
        size = 0
        while self.byte() != 34:
            char = self.byte()
            check(char >= 32, "sync_control_json")
            self.pos += 1
            if char == 92:
                escape = self.byte()
                self.pos += 1
                if escape == 117:
                    char = self.hex4()
                    if 0xD800 <= char <= 0xDBFF:
                        self.take(92)
                        self.take(117)
                        low = self.hex4()
                        check(0xDC00 <= low <= 0xDFFF, "sync_control_unicode")
                        char = 0x10000 + ((char - 0xD800) << 10) + low - 0xDC00
                    else:
                        check(not 0xDC00 <= char <= 0xDFFF, "sync_control_unicode")
                else:
                    mapping = {34: 34, 92: 92, 47: 47, 98: 8, 102: 12, 110: 10, 114: 13, 116: 9}
                    check(escape in mapping, "sync_control_json")
                    char = mapping[escape]
            elif char >= 128:
                if 0xC2 <= char <= 0xDF:
                    count, minimum, char = 1, 0x80, char & 31
                elif 0xE0 <= char <= 0xEF:
                    count, minimum, char = 2, 0x800, char & 15
                else:
                    check(0xF0 <= char <= 0xF4, "sync_control_unicode")
                    count, minimum, char = 3, 0x10000, char & 7
                for _ in range(count):
                    byte = self.byte()
                    check(0x80 <= byte <= 0xBF, "sync_control_unicode")
                    self.pos += 1
                    char = (char << 6) | (byte & 63)
                check(minimum <= char <= 0x10FFFF and not 0xD800 <= char <= 0xDFFF, "sync_control_unicode")
            size += 1
            check(size <= 4096, "sync_control_string")
            if build:
                chars.append(chr(char))
        self.pos += 1
        return "".join(chars) if build else None

    def value(self, depth, build):
        check(depth <= 8, "sync_control_tree")
        self.node()
        self.space()
        char = self.byte()
        if char == 34:
            return self.string(build)
        if char in (123, 91):
            self.pos += 1
            object_value, ending = char == 123, 125 if char == 123 else 93
            output = ({} if object_value else []) if build else None
            seen = set() if object_value else None
            self.space()
            count = 0
            if self.byte() != ending:
                while True:
                    count += 1
                    check(count <= 32, "sync_control_tree")
                    self.space()
                    if object_value:
                        self.node()
                        key = self.string(True)
                        check(key not in seen, "sync_control_duplicate")
                        seen.add(key)
                        self.space()
                        self.take(58)
                    child = self.value(depth + 1, build)
                    if build:
                        if object_value:
                            output[key] = child
                        else:
                            output.append(child)
                    self.space()
                    if self.byte() != 44:
                        break
                    self.pos += 1
            self.take(ending)
            return output
        for word, value in ((b"true", True), (b"false", False), (b"null", None)):
            if char == word[0]:
                for byte in word:
                    self.take(byte)
                return value
        negative = char == 45
        if negative:
            self.pos += 1
        check(48 <= self.byte() <= 57, "sync_control_number")
        zero = self.byte() == 48
        number, count = 0, 0
        while 48 <= self.byte() <= 57:
            number = number * 10 + self.byte() - 48
            self.pos += 1
            count += 1
            check(count <= 20, "sync_control_number")
        check((not zero or count == 1) and not (negative and number == 0), "sync_control_number")
        check(number < 2**64, "sync_control_number")
        return -number if negative else number


def parse_control(data, start, stop):
    """Two bounded passes; build the DTO only after strict shape preflight."""
    reader = _Reader(data, start, stop)
    try:
        reader.space()
        check(reader.byte() == 123, "sync_control_json")
        reader.value(0, False)
        reader.space()
        check(reader.pos == stop, "sync_control_json")
        reader.pos, reader.nodes = start, 0
        return reader.value(0, True)
    finally:
        reader.data = None
