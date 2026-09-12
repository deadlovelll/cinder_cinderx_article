# Portions copyright (c) Meta Platforms, Inc. and affiliates.

# pyre-strict

"""Package for compiling Python source code

There are several functions defined at the top level that are imported
from modules contained in the package.

compile(source, filename, mode, flags=None, dont_inherit=None)
    Returns a code object.  A replacement for the builtin compile() function.

compileFile(filename)
    Generates a .pyc file by compiling filename.
"""

import ast
import dis
import sys
from io import StringIO
from types import CodeType
from typing import Any, Iterator

from .opcodes import STATIC_CONST_OPCODES, STATIC_DEOPT, STATIC_OPNAMES
from .pycodegen import CinderCodeGenerator, compile, compile_code, compileFile


def make_static_instr(instr: dis.Instruction, co: object) -> dis.Instruction:
    # Report the unspecialized form: the adaptive interpreter rewrites static
    # opcodes in place, and a disassembly is a reading of the code as written.
    opnum = STATIC_DEOPT.get(instr.opcode, instr.opcode)
    if opnum in STATIC_CONST_OPCODES:
        # pyre-fixme[21]: Could not find name `_get_code_object` in `dis` (stubbed).
        from dis import _get_code_object

        return dis.Instruction(
            STATIC_OPNAMES[opnum],
            instr[1],
            instr.arg,
            _get_code_object(co).co_consts[instr.arg],
            *instr[4:],
        )
    return dis.Instruction(STATIC_OPNAMES[opnum], *instr[1:])


def static_instructions(x: object) -> Iterator[dis.Instruction]:
    """dis.get_instructions with the static opcodes named and their caches hidden.

    dis walks the code stream a word at a time and has no idea that a static
    opcode reserves inline cache units behind it, so it decodes those units as
    instructions. While they are zero that is merely noisy; once the adaptive
    interpreter has written a cache into them they decode as arbitrary opcodes,
    and a name-bearing one indexes straight off the end of co_names.
    """
    from .opcodes import _inline_cache_entries

    resume_at = -1
    extended = False
    for instr in dis.get_instructions(x):
        if instr.offset < resume_at:
            continue
        if instr.opname == "EXTENDED_OPCODE":
            extended = True
            yield instr
        elif extended and instr.opname != "EXTENDED_ARG":
            extended = False
            static = make_static_instr(instr, x)
            # pyre-fixme[16]: Module `opcode` has no attribute
            #  `_inline_cache_entries`.
            caches = _inline_cache_entries.get(static.opname, 0)
            resume_at = instr.offset + 2 + 2 * caches
            yield static
        else:
            yield instr


def get_disassembly_as_string(co: object, recurse: bool = False) -> str:
    s = StringIO()
    if sys.version_info < (3, 14):
        # pyrefly: ignore [bad-argument-type]
        dis.dis(co, file=s)
        return s.getvalue()

    # pyre-fixme[21]: Could not find name `Formatter` in `dis` (stubbed).
    # pyre-fixme[21]: Could not find name `_get_code_object` in `dis` (stubbed).
    from dis import _get_code_object, Formatter

    formatter = Formatter(file=s, offset_width=3)
    for instr in static_instructions(co):
        formatter.print_instruction(instr, False)

    if recurse:
        for const in _get_code_object(co).co_consts:
            if isinstance(const, CodeType):
                s.write(f"\nDisassembly of {const!r}:\n")
                s.write(get_disassembly_as_string(const, recurse=True))

    return s.getvalue()


def exec_cinder(
    source: str | bytes | ast.Module | ast.Expression | ast.Interactive | CodeType,
    locals: dict[str, Any],
    globals: dict[str, Any],
    modname: str = "<module>",
) -> None:
    if isinstance(source, CodeType):
        code = source
    else:
        code = compile_code(
            source, "<module>", "exec", compiler=CinderCodeGenerator, modname=modname
        )

    exec(code, locals, globals)


__all__ = (
    "compile",
    "compile_code",
    "compileFile",
    "exec_cinder",
    "get_disassembly_as_string",
    "make_static_instr",
    "static_instructions",
)
