"""
jpamb.jvm

This module provides primitives to talk about the contents of java bytefiles, 
as well as names and types.

It is recommended to import this module qualified 

from jpamb import jvm

"""

from collections import namedtuple
from functools import total_ordering
import re
from abc import ABC
from dataclasses import dataclass
from typing import *  # type: ignore
import typing

type_instances = dict()


@total_ordering
class Type(ABC):
    """A jvm type"""

    def encode(self) -> str: ...

    @staticmethod
    def decode(input) -> tuple["Type", str]:
        r, stack = None, []
        i = 0
        r = None
        while i < len(input):
            match input[i]:
                case "Z":
                    r = Boolean
                case "I":
                    r = Int
                case "B":
                    r = Byte
                case "C":
                    r = Char
                case "[":  # ]
                    stack.append(Array)
                    i += 1
                    continue
                case _:
                    raise ValueError(f"Unknown type {input[i]}")
            break
        else:
            raise ValueError(f"Could not decode {input}")

        assert r is not None

        key = tuple(stack + [r])

        if (res := type_instances.get(key, None)) is None:
            res = r()
            for k in reversed(stack):
                res = k(res)
            type_instances[key] = res

        return res, input[i + 1 :]

    def __lt__(self, other):
        return self.encode() <= other.encode()

    def __eq__(self, other):
        return self.encode() <= other.encode()


@dataclass(frozen=True)
class Boolean(Type):
    """
    A boolean
    """

    _instance = None

    def __new__(cls) -> "Boolean":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def encode(self):
        return "Z"


@dataclass(frozen=True)
class Int(Type):
    """
    A 32bit signed integer
    """

    _instance = None

    def __new__(cls) -> "Int":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def encode(self):
        return "I"


@dataclass(frozen=True)
class Byte(Type):
    """
    An 8bit signed integer
    """

    _instance = None

    def __new__(cls) -> "Byte":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def encode(self):
        return "B"


@dataclass(frozen=True)
class Char(Type):
    """
    An 16bit character
    """

    _instance = None

    def __new__(cls) -> "Char":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def encode(self):
        return "C"


@dataclass(frozen=True, order=True)
class Array(Type):
    """
    A list of types
    """

    _instance = dict()

    def __new__(cls, subtype) -> "Array":
        if subtype not in cls._instance:
            cls._instance[subtype] = super().__new__(cls)
        return cls._instance[subtype]

    contains: Type

    def __post_init__(self):
        assert self.contains is not None

    def encode(self):
        return "[" + self.contains.encode()  # ]


@dataclass(frozen=True, order=True)
class ParameterType:
    """A list of parameters types"""

    _elements: tuple[Type, ...]

    def __getitem__(self, index):
        return self._elements.__getitem__(index)

    def __len__(self):
        return self._elements.__len__()

    def encode(self):
        return "".join(e.encode() for e in self._elements)

    @staticmethod
    def decode(input: str) -> "ParameterType":
        params = []
        while input:
            (tt, input) = Type.decode(input)
            params.append(tt)

        return ParameterType(tuple(params))


@dataclass(frozen=True, order=True)
class ClassName:
    """The name of a class, inner classes must use the $ syntax"""

    _as_string: str

    @property
    def packages(self) -> list[str]:
        """Get a list of packages"""
        return self.parts[:-1]

    @property
    def name(self) -> str:
        """Get the unqualified name"""
        return self.parts[-1]

    @property
    def parts(self) -> list[str]:
        """Get the elements of the name"""
        return self._as_string.split(".")

    def encode(self) -> str:
        return self._as_string

    @staticmethod
    def decode(input: str) -> "ClassName":
        return ClassName(input)

    @staticmethod
    def from_parts(*args: str) -> "ClassName":
        return ClassName(".".join(args))


METHOD_ID_RE_RAW = r"(?P<method_name>.*)\:\((?P<params>.*)\)(?P<return>.*)"
METHOD_ID_RE = re.compile(METHOD_ID_RE_RAW)


@dataclass(frozen=True, order=True)
class MethodID:
    """A method ID consist of a name, a list of parameter types and a return type."""

    name: str
    params: ParameterType
    return_type: Type | None

    @staticmethod
    def decode(input: str):
        if (match := METHOD_ID_RE.match(input)) is None:
            raise ValueError("invalid method name: %r", input)

        return_type = None
        if match["return"] != "V":
            return_type, more = Type.decode(match["return"])
            if more:
                raise ValueError(
                    f"could not decode method id, bad return type {match['return']!r}"
                )

        return MethodID(
            name=match["method_name"],
            params=ParameterType.decode(match["params"]),
            return_type=return_type,
        )

    def encode(self) -> str:
        rt = self.return_type.encode() if self.return_type is not None else "V"
        return f"{self.name}:({self.params.encode()}){rt}"


class Encodable(Protocol):
    def encode(self) -> str: ...


ABSOLUTE_RE = re.compile(r"(?P<class_name>.+)\.(?P<rest>.*)")


@dataclass(frozen=True, order=True)
class Absolute[T: Encodable]:
    classname: ClassName
    extension: T

    @staticmethod
    def decode(input, decode: Callable[[str], T]) -> "Absolute":
        if (match := ABSOLUTE_RE.match(input)) is None:
            raise ValueError("invalid absolute method name: %r", input)

        return Absolute(ClassName.decode(match["class_name"]), decode(match["rest"]))

    def encode(self) -> str:
        return f"{self.classname.encode()}.{self.extension.encode()}"


@dataclass(frozen=True, order=True)
class Value:
    type: Type
    value: Any

    @staticmethod
    def decode_many(input) -> list["Value"]:
        vp = ValueParser(input)
        values = vp.parse_comma_seperated_values()
        vp.eof()
        return values

    @staticmethod
    def decode(input) -> list["Value"]:
        vp = ValueParser(input)
        value = vp.parse_comma_seperated_values()
        vp.eof()
        return value

    def encode(self) -> str:
        match self.type:
            case Boolean():
                return "true" if self.value else "false"
            case Int():
                return str(self.value)
            case Char():
                return f"'{self.value}'"
            case Array(content):
                match content:
                    case Int():
                        ints = ", ".join(map(str, self.value))
                        return f"[I:{ints}]"
                    case Char():
                        chars = ", ".join(map(lambda a: f"'{a}'", self.value))
                        return f"[C:{chars}]"
                    case _:
                        raise NotImplemented()

        return self.value

    @staticmethod
    def int(n: int):
        return Value(Int(), n)

    @staticmethod
    def boolean(n: bool):
        return Value(Boolean(), n)

    @staticmethod
    def char(char: str):
        assert len(char) == 1
        return Value(Char(), char)

    @staticmethod
    def array(type: Type, content: Iterable):
        return Value(Array(type), tuple(content))


@dataclass
class ValueParser:
    Token = namedtuple("Token", "kind value")

    input: str
    head: Optional["ValueParser.Token"]
    _tokens: Iterator["ValueParser.Token"]

    def __init__(self, input) -> None:
        self.input = input
        self._tokens = ValueParser.tokenize(input)
        self.next()

    @staticmethod
    def tokenize(string):
        token_specification = [
            ("OPEN_ARRAY", r"\[[IC]:"),
            ("CLOSE_ARRAY", r"\]"),
            ("INT", r"-?\d+"),
            ("BOOL", r"true|false"),
            ("CHAR", r"'[^']'"),
            ("COMMA", r","),
            ("SKIP", r"[ \t]+"),
        ]
        tok_regex = "|".join(f"(?P<{n}>{m})" for n, m in token_specification)

        for m in re.finditer(tok_regex, string):
            kind, value = m.lastgroup, m.group()
            if kind == "SKIP":
                continue
            yield ValueParser.Token(kind, value)

    @staticmethod
    def parse(string) -> list[Value]:
        return ValueParser(string).parse_comma_seperated_values()

    def next(self):
        try:
            self.head = next(self._tokens)
        except StopIteration:
            self.head = None

    def expected(self, expected) -> NoReturn:
        raise ValueError(f"Expected {expected} but got {self.head} in {self.input}")

    def expect(self, expect) -> Token:
        head = self.head
        if head is None:
            self.expected(repr(expect))
        elif expect != head.kind:
            self.expected(repr(expect))
        self.next()
        return head

    def eof(self):
        if self.head is None:
            return
        self.expected("end of file")

    def parse_value(self):
        next = self.head or self.expected("token")
        match next.kind:
            case "INT":
                return Value.int(self.parse_int())
            case "CHAR":
                return Value.char(self.parse_char())
            case "BOOL":
                return Value.boolean(self.parse_bool())
            case "OPEN_ARRAY":
                return self.parse_array()
        self.expected("char")

    def parse_int(self):
        tok = self.expect("INT")
        return int(tok.value)

    def parse_bool(self):
        tok = self.expect("BOOL")
        return tok.value == "true"

    def parse_char(self):
        tok = self.expect("CHAR")
        return tok.value[1]

    def parse_array(self):
        key = self.expect("OPEN_ARRAY")
        if key.value == "[I:":  # ]
            type = Array(Int())
            parser = self.parse_int
        elif key.value == "[C:":  # ]
            type = Array(Char())
            parser = self.parse_char
        else:
            self.expected("int or char array")

        inputs = self.parse_comma_seperated_values(parser, "CLOSE_ARRAY")

        self.expect("CLOSE_ARRAY")

        return Value(type, tuple(inputs))

    def parse_comma_seperated_values(self, parser=None, end_by=None):
        if self.head is None:
            return []

        if end_by is not None and self.head.kind == end_by:
            return []

        parser = parser or self.parse_value
        inputs = [parser()]

        while self.head and self.head.kind == "COMMA":
            self.next()
            inputs.append(parser())

        return inputs
