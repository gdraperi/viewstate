from datetime import datetime

from .exceptions import ViewStateException


class ParserMeta(type):

    def __init__(cls, name, bases, namespace):
        super(ParserMeta, cls).__init__(name, bases, namespace)
        if not hasattr(cls, 'registry'):
            cls.registry = {}
        if hasattr(cls, 'marker'):
            marker = getattr(cls, 'marker')
            if type(marker) not in (tuple, list):
                marker = [marker]
            for m in marker:
                cls.registry[m] = cls


class Parser(metaclass=ParserMeta):

    @staticmethod
    def parse(b):
        marker, remain = b[0], b[1:]
        try:
            return Parser.registry[marker]().parse(remain)
        except KeyError:
            raise ViewStateException(f'Unknown marker {marker}')


class Const(Parser):

    def parse(self, remain):
        return self.const, remain


class NoneConst(Const):
    marker = 0x64
    const = None


class EmptyConst(Const):
    marker = 0x65
    const = ''


class ZeroConst(Const):
    marker = 0x66
    const = 0


class TrueConst(Const):
    marker = 0x67
    const = True


class FalseConst(Const):
    marker = 0x68
    const = False


class Integer(Parser):
    marker = 0x02

    @staticmethod
    def parse(b):
        n = 0
        bits = 0
        i = 0
        while (bits < 32):
            tmp = b[i]
            i += 1
            n |= (tmp & 0x7f) << bits
            if not (tmp & 0x80):
                return n, b[i:]
            bits += 7
        return n, b[i:]  # overflow


class String(Parser):
    marker = (0x05, 0x1e)

    @staticmethod
    def parse(b):
        n = b[0]
        n, remain = Integer.parse(b)
        s = remain[:n]
        return s.decode(), remain[n:]


class Enum(Parser):
    marker = 0x0b

    @staticmethod
    def parse(b):
        if b[0] in (0x29, 0x2a):
            enum, remain = String.parse(b[1:])
        elif b[0] == 0x2b:
            enum, remain = Integer.parse(b[1:])
        val, remain = Integer.parse(remain)  # unsure about this part
        final = 'Enum: {}, val: {}'.format(enum, val)
        return final, remain


class Color(Parser):
    marker = 0x0a

    @staticmethod
    def parse(b):
        # No specification for color parsing, we're assuming it's just two bytes
        # One example we have is that `\n\x91\x01` is parsed as `Color: Color [Salmon]`
        # Originally reported in https://github.com/yuvadm/viewstate/issues/2
        return 'Color: unknown', b[2:]


class Pair(Parser):
    marker = 0x0f

    @staticmethod
    def parse(b):
        first, remain = Parser.parse(b)
        second, remain = Parser.parse(remain)
        return (first, second), remain


class Triplet(Parser):
    marker = 0x10

    @staticmethod
    def parse(b):
        first, remain = Parser.parse(b)
        second, remain = Parser.parse(remain)
        third, remain = Parser.parse(remain)
        return (first, second, third), remain


class Datetime(Parser):
    marker = 0x06

    @staticmethod
    def parse(b):
        #print([x for x in b[:8]])
        return datetime(2000, 1, 1), b[8:]


class Unit(Parser):
    marker = 0x1b

    @staticmethod
    def parse(b):
        #print([x for x in b[:12]])
        return 'Unit: ', b[12:]


class RGBA(Parser):
    marker = 0x09

    @staticmethod
    def parse(b):
        return 'RGBA({},{},{},{})'.format(*b[:4]), b[4:]


class StringArray(Parser):
    marker = 0x15

    @staticmethod
    def parse(b):
        n, remain = Integer.parse(b)
        l = []
        for _ in range(n):
            if not remain[0]:
                val, remain = '', remain[1:]
            else:
                val, remain = String.parse(remain)
            l.append(val)
        return l, remain


class Array(Parser):
    marker = 0x16

    @staticmethod
    def parse(b):
        n, remain = Integer.parse(b)
        l = []
        for _ in range(n):
            val, remain = Parser.parse(remain)
            l.append(val)
        return l, remain


class StringRef(Parser):
    marker = 0x1f

    @staticmethod
    def parse(b):
        val, remain = Integer.parse(b)
        return 'Stringref #{}'.format(val), remain


class FormattedString(Parser):
    marker = 0x28

    @staticmethod
    def parse(b):
        if b[0] == 0x29:
            s1, remain = String.parse(b[1:])
            s2, remain = String.parse(remain)
            return 'Formatted string: {} {}'.format(s2, s1), remain
        elif b[0] == 0x2b:
            i, remain = Integer.parse(b[1:])
            s, remain = String.parse(remain)
            return 'Formatted string: {} type ref {}'.format(s, i), remain
        else:
            raise ViewStateException('Unknown formatted string type marker {}'.format(b[:20]))


class SparseArray(Parser):
    marker = 0x3c

    @staticmethod
    def parse(b):
        type, remain = Type.parse(b)
        length, remain = Integer.parse(remain)
        n, remain = Integer.parse(remain)
        l = [None] * length
        for _ in range(n):
            idx, remain = Integer.parse(remain)
            val, remain = Parser.parse(remain)
            l[idx] = val
        return l, remain


class Dict(Parser):
    marker = 0x18

    @staticmethod
    def parse(b):
        n = b[0]
        d = {}
        remain = b[1:]
        for _ in range(n):
            k, remain = Parser.parse(remain)
            v, remain = Parser.parse(remain)
            d[k] = v
        return d, remain

class Type(Parser):

    @staticmethod
    def parse(b):
        if b[0] in (0x29, 0x2a):
            return String.parse(b[1:])
        elif b[0] == 0x2b:
            return Integer.parse(b[1:])
        else:
            raise ViewStateException('Unknown type flag at {} bytes {}'.format(len(b), b[:20]))

class TypedArray(Parser):
    marker = 0x14

    @staticmethod
    def parse(b):
        typeval, remain = Type.parse(b)
        n, remain = Integer.parse(remain)
        l = []
        for _ in range(n):
            val, remain = Parser.parse(remain)
            l.append(val)
        return l, remain
