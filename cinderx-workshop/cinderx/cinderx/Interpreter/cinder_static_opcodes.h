// Copyright (c) Meta Platforms, Inc. and affiliates.

// Shape of a Static Python instruction, shared by the interpreter and the JIT.
//
// From 3.14 on, the static opcodes no longer own numbers in CPython's opcode
// space; they are encoded as a two-unit instruction
//
//     [EXTENDED_OPCODE | stack effects] [static opcode | oparg] [cache]...
//
// followed by the inline cache units the static compiler reserved for them.
// Both the interpreter (to find the next instruction) and the JIT (to walk the
// bytecode) have to agree with the compiler about how many of those there are,
// which is why the answer lives in one place. The counts must match
// `inline_cache_entries` in PythonLib/opcodes/3_14/opcode.py.
//
// Note that the low byte of a static opcode collides with an ordinary CPython
// opcode -- STORE_LOCAL_CACHED & 0xFF is GET_ITER -- so these tables may only
// be consulted for a unit that is known to sit behind an EXTENDED_OPCODE.

#pragma once

#include "cinderx/Interpreter/cinder_opcode.h"

#if PY_VERSION_HEX >= 0x030E0000

// Number of inline cache code units that follow a static opcode.
//
// A cache unit carries one payload byte, not two: see Ci_cache_write.
static inline int Ci_extop_cache_entries(int extop) {
  switch (extop) {
    case POP_JUMP_IF_ZERO:
    case POP_JUMP_IF_NONZERO:
      return 1;
    case STORE_LOCAL:
    case STORE_LOCAL_CACHED:
      return 2;
    case LOAD_FIELD:
    case LOAD_OBJ_FIELD:
    case LOAD_PRIMITIVE_FIELD:
    case STORE_FIELD:
    case STORE_OBJ_FIELD:
    case STORE_PRIMITIVE_FIELD:
    case LOAD_METHOD_STATIC:
    case LOAD_METHOD_STATIC_CACHED:
    case CAST:
    case CAST_CACHED:
    case TP_ALLOC:
    case TP_ALLOC_CACHED:
    case BUILD_CHECKED_LIST:
    case BUILD_CHECKED_LIST_CACHED:
    case BUILD_CHECKED_MAP:
    case BUILD_CHECKED_MAP_CACHED:
    case INVOKE_FUNCTION:
    case INVOKE_FUNCTION_CACHED:
      return 4;
    default:
      return 0;
  }
}

/* A specialization payload, one byte per cache unit, little-endian.
 *
 * Only the arg byte of each unit is used; the opcode byte is left at CACHE.
 * CPython walks a code object one unit at a time -- deopt_code, the
 * instrumentation, dis -- and cannot know that a static opcode reserves cache
 * units behind it, because the byte naming that opcode means something else in
 * CPython's own table. So it reads these units as instructions. A unit whose
 * opcode byte happened to name an opcode with inline caches of its own would
 * send that walk past the end of the code object, and in _PyCode_GetCode that
 * is a write out of bounds. Keeping the opcode byte at CACHE makes every cache
 * unit read as exactly what it is: a cache.
 */
static inline void
Ci_cache_write(_Py_CODEUNIT* cache, uint32_t value, int units) {
  for (int i = 0; i < units; i++) {
    cache[i].op.code = 0;
    cache[i].op.arg = (uint8_t)(value >> (8 * i));
  }
}

static inline uint32_t Ci_cache_read(const _Py_CODEUNIT* cache, int units) {
  uint32_t value = 0;
  for (int i = 0; i < units; i++) {
    value |= (uint32_t)cache[i].op.arg << (8 * i);
  }
  return value;
}

// Map a specialized static opcode back to the one the compiler emitted.
//
// Specializing only rewrites the opcode byte: the oparg still indexes the same
// co_consts entry and the instruction is still the same length, so the base
// form remains a faithful reading of the instruction. That is what lets the
// JIT compile a function the interpreter has already specialized.
static inline int Ci_extop_deopt(int extop) {
  switch (extop) {
    case STORE_LOCAL_CACHED:
      return STORE_LOCAL;
    case LOAD_OBJ_FIELD:
    case LOAD_PRIMITIVE_FIELD:
      return LOAD_FIELD;
    case STORE_OBJ_FIELD:
    case STORE_PRIMITIVE_FIELD:
      return STORE_FIELD;
    case LOAD_METHOD_STATIC_CACHED:
      return LOAD_METHOD_STATIC;
    case INVOKE_FUNCTION_CACHED:
    case INVOKE_INDIRECT_CACHED:
      return INVOKE_FUNCTION;
    case BUILD_CHECKED_LIST_CACHED:
      return BUILD_CHECKED_LIST;
    case BUILD_CHECKED_MAP_CACHED:
      return BUILD_CHECKED_MAP;
    case CAST_CACHED:
      return CAST;
    case TP_ALLOC_CACHED:
      return TP_ALLOC;
    default:
      return extop;
  }
}

#endif
