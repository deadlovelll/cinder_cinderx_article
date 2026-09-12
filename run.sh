#!/usr/bin/env bash
# Build the interpreters, install the dependencies, run the benches and the workshop.
#
# One command does the campaign: ./run.sh all
# Each stage is also a subcommand, and every stage is idempotent, so a run that
# failed halfway can be resumed by calling it again.
#
#   ./run.sh check         host preconditions; refuses a host that cannot measure
#   ./run.sh sources       clone CPython, the Meta fork and CinderX at pinned refs
#   ./run.sh interpreters  build all three, with identical flags
#   ./run.sh deps          one venv per interpreter, CinderX into the stock one
#   ./run.sh probe         report what this build can actually do, before measuring
#   ./run.sh dialect       verify the Static Python reference and emit REFERENCE.md
#   ./run.sh bench         the microbenches, through pyperf
#   ./run.sh workshop      seed the fixture, then the ladder and the kernel matrix
#   ./run.sh all           every stage above, in order
#   ./run.sh clean         drop builds and venvs; sources and results are kept
#
# The database belongs on another host: set RECSYS_DB_HOST. So does the load
# generator. Running either beside the service measures the host, not the runtime.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$ROOT/cinderx-workshop"
BUILD="$ROOT/build"
LOGS="$BUILD/logs"
MANIFEST="$BUILD/manifest.json"

# Pinned, because "the latest" is not a measurement. Override to move a pin.
CPYTHON_REF="${CPYTHON_REF:-v3.14.6}"
CINDER_REF="${CINDER_REF:-meta/3.14}"
CINDERX_REF="${CINDERX_REF:-main}"
CINDERX_VERSION="${CINDERX_VERSION:-2026.9.7.0}"

CPYTHON_URL="${CPYTHON_URL:-https://github.com/python/cpython.git}"
CINDER_URL="${CINDER_URL:-https://github.com/facebookincubator/cinder.git}"
CINDERX_URL="${CINDERX_URL:-https://github.com/facebookincubator/cinderx.git}"

JOBS="${JOBS:-$( (nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4) )}"
# PGO and LTO on by default: distributions ship optimised builds, and a baseline
# that is not optimised would flatter every rung measured against it.
PGO="${PGO:-1}"
# Set to 1 to keep going past a stage that failed. Off by default: a campaign with
# a hole in it is worse than one that stopped where the hole is.
KEEP_GOING="${KEEP_GOING:-0}"

STOCK="$BUILD/stock"
TIER2="$BUILD/tier2"
FORK="$BUILD/fork"

# An interpreter that already exists can be used instead of building one. This is
# for a smoke test of the pipeline, not for a publishable run: three builds with
# identical flags are what make the ladder's rungs one delta apart, and a distro
# interpreter shares none of those flags with the other two.
STOCK_PYTHON="${STOCK_PYTHON:-$STOCK/bin/python3.14}"
TIER2_PYTHON="${TIER2_PYTHON:-$TIER2/bin/python3.14}"
FORK_PYTHON="${FORK_PYTHON:-$FORK/bin/python3.14}"
VENV_STOCK="$BUILD/venv-stock"
VENV_TIER2="$BUILD/venv-tier2"
VENV_FORK="$BUILD/venv-fork"

# Passed to every bench. Empty for a real campaign, which is what pyperf's own
# defaults are for; set it to smoke-test the stage without spending the hours:
#   BENCH_ARGS="--processes 1 --values 2 --warmups 2" ./run.sh bench
BENCH_ARGS="${BENCH_ARGS:-}"

RESULTS="${BENCH_RESULTS_DIR:-$ROOT/results}"
LADDER_OUT="$ROOT/service/load/results"

# ---------------------------------------------------------------------------
# plumbing
# ---------------------------------------------------------------------------

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
info() { printf '   %s\n' "$*"; }
warn() { printf '\033[33m   ! %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31m   x %s\033[0m\n' "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

# Run a stage, and let KEEP_GOING decide whether a failure is fatal.
stage() {
  local name="$1"; shift
  if "$@"; then
    return 0
  fi
  if [ "$KEEP_GOING" = "1" ]; then
    warn "stage '$name' failed; continuing because KEEP_GOING=1"
    return 0
  fi
  die "stage '$name' failed"
}

# Record what was actually built, so a number can be traced to a tree.
record() {
  mkdir -p "$BUILD"
  python3 - "$MANIFEST" "$1" "$2" <<'PY'
import json, os, sys
path, key, value = sys.argv[1], sys.argv[2], sys.argv[3]
data = {}
if os.path.exists(path):
    with open(path) as fh:
        data = json.load(fh)
data[key] = value
with open(path, "w") as fh:
    json.dump(data, fh, indent=1, sort_keys=True)
PY
}

is_linux() { [ "$(uname -s)" = "Linux" ]; }

# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

cmd_check() {
  say "host preconditions"
  local missing=()
  for tool in git curl make python3; do
    have "$tool" || missing+=("$tool")
  done
  have cc || have gcc || have clang || missing+=("a C compiler")
  have uv || missing+=("uv (https://docs.astral.sh/uv/)")
  have k6 || missing+=("k6 (the workshop's load generator)")
  [ ${#missing[@]} -eq 0 ] || die "missing: ${missing[*]}"
  info "tools: git curl make cc uv k6 present"

  if ! is_linux; then
    warn "$(uname -s), not Linux. The fork, lazy imports, the parallel collector,"
    warn "AOT loading, smaps and perf are Linux-only; those stages will be skipped"
    warn "and the campaign will be incomplete. Publishable runs need Linux."
  fi

  # The build needs headers that CPython silently builds without, then ships a
  # crippled interpreter: no ssl means no pip, no sqlite3 means no pyperf store.
  if is_linux && have dpkg-query; then
    local pkgs=(libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev
                libffi-dev liblzma-dev uuid-dev)
    local absent=()
    for p in "${pkgs[@]}"; do
      dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok" || absent+=("$p")
    done
    if [ ${#absent[@]} -gt 0 ]; then
      warn "development headers absent: ${absent[*]}"
      warn "install them, or the interpreters build without ssl/sqlite/lzma"
    else
      info "build headers present"
    fi
  fi

  # The measurement preconditions proper: isolated cores, governor, ASLR. This
  # refuses to pass on a host that cannot hold still, which is the point.
  say "measurement preconditions"
  # The verdict, not the exit code: system.py reports DEGRADED and still exits 0,
  # so a host that cannot hold still would otherwise pass this stage in silence.
  local pre
  pre="$(python3 "$ROOT/bench/harness/system.py" 2>&1 || true)"
  printf '%s\n' "$pre" | sed 's/^/   /'
  if ! printf '%s' "$pre" | grep -q "preflight: OK"; then
    warn "the host is not tuned for measurement; see the complaints above"
    warn "benches will still run, but CX_BENCH_STRICT=1 will refuse them"
  fi

  if [ -z "${RECSYS_DB_HOST:-}" ]; then
    warn "RECSYS_DB_HOST is unset: the workshop stage will refuse to run"
  elif [ "${RECSYS_DB_HOST}" = "localhost" ] || [ "${RECSYS_DB_HOST}" = "127.0.0.1" ]; then
    warn "RECSYS_DB_HOST is local: the database will compete with the service"
    warn "for the cores being measured. Put it on another host."
  else
    info "database host: ${RECSYS_DB_HOST}"
  fi
}

# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------

# Shallow clone at a ref, or leave an existing tree alone.
fetch() {
  local url="$1" ref="$2" dest="$3"
  if [ -d "$dest" ]; then
    info "$(basename "$dest"): present, left as is"
  else
    say "cloning $(basename "$dest") at $ref"
    git clone --depth 1 --branch "$ref" "$url" "$dest" 2>&1 | tail -2
  fi
  local rev="unknown"
  if [ -d "$dest/.git" ]; then
    rev="$(git -C "$dest" rev-parse HEAD)"
  else
    warn "$(basename "$dest"): no git metadata, so the manifest cannot pin it"
  fi
  record "$(basename "$dest")_ref" "$ref"
  record "$(basename "$dest")_commit" "$rev"
  info "$(basename "$dest") commit: $rev"
}

# Read PY_VERSION straight out of a source tree, before anything is built.
tree_version() {
  sed -n 's/^#define PY_VERSION *"\(.*\)".*/\1/p' "$1/Include/patchlevel.h" 2>/dev/null
}

cmd_sources() {
  mkdir -p "$WORK"
  fetch "$CPYTHON_URL" "$CPYTHON_REF" "$WORK/cpython"
  fetch "$CINDER_URL"  "$CINDER_REF"  "$WORK/cinder"
  fetch "$CINDERX_URL" "$CINDERX_REF" "$WORK/cinderx"

  # The fork rung claims to isolate the fork. It only does so if the fork and the
  # baseline share a base version: the fork lags upstream, and comparing 3.14.5+meta
  # against 3.14.6 measures the fork plus a patch bump and attributes both to the
  # fork. Cheap to detect here, expensive to notice in a finished table.
  local sv fv
  sv="$(tree_version "$WORK/cpython")"
  fv="$(tree_version "$WORK/cinder")"
  record "cpython_tree_version" "${sv:-unknown}"
  record "cinder_tree_version" "${fv:-unknown}"
  if [ -n "$sv" ] && [ -n "$fv" ]; then
    local sbase="${sv%%+*}" fbase="${fv%%+*}"
    if [ "$sbase" != "$fbase" ]; then
      warn "baseline is $sv but the fork is $fv"
      warn "rung 03 would then conflate the fork with a patch bump"
      warn "build the baseline at the fork's base: CPYTHON_REF=v$fbase ./run.sh interpreters"
    else
      info "baseline and fork share base $sbase"
    fi
  fi
}

# ---------------------------------------------------------------------------
# interpreters
# ---------------------------------------------------------------------------

# Build one interpreter. All three get the same flags; only $4 differs, which is
# what makes the ladder's rungs one delta apart instead of several.
build_python() {
  local src="$1" prefix="$2" label="$3" extra="${4:-}"
  if [ -x "$prefix/bin/python3.14" ]; then
    info "$label: already built at $prefix"
    return 0
  fi
  [ -d "$src" ] || die "$label: source tree $src is missing; run ./run.sh sources"
  say "building $label"
  mkdir -p "$LOGS"
  local log="$LOGS/build-$label.log"
  local opt=()
  if [ "$PGO" = "1" ]; then
    opt=(--enable-optimizations --with-lto)
    info "PGO and LTO on; this takes a while"
  else
    warn "PGO off: the baseline is slower than a distribution build"
  fi
  (
    cd "$src"
    make distclean >/dev/null 2>&1 || true
    ./configure --prefix="$prefix" "${opt[@]}" ${extra:+$extra}
    make -j"$JOBS"
    make install
  ) >"$log" 2>&1 || { tail -30 "$log"; die "$label: build failed, see $log"; }
  "$prefix/bin/python3.14" -VV | sed 's/^/   /'
  record "${label}_version" "$("$prefix/bin/python3.14" -VV | tr '\n' ' ')"
}

cmd_interpreters() {
  build_python "$WORK/cpython" "$STOCK" "stock"
  build_python "$WORK/cpython" "$TIER2" "tier2" "--enable-experimental-jit"
  if is_linux; then
    build_python "$WORK/cinder" "$FORK" "fork"
  else
    warn "fork build skipped: not Linux"
  fi
  # A build without ssl or sqlite looks fine until pip or pyperf needs them.
  for p in "$STOCK_PYTHON" "$TIER2_PYTHON" "$FORK_PYTHON"; do
    [ -x "$p" ] || continue
    "$p" - <<'PY' || die "$p: incomplete build"
import sys
missing = []
for mod in ("ssl", "sqlite3", "lzma", "bz2", "zlib", "ctypes", "readline"):
    try:
        __import__(mod)
    except ImportError:
        missing.append(mod)
if missing:
    print("   x missing modules:", ", ".join(missing))
    sys.exit(1)
print(f"   {sys.executable}: stdlib complete")
PY
  done
}

# ---------------------------------------------------------------------------
# deps
# ---------------------------------------------------------------------------

# One venv per interpreter, all from the same lock, so the only difference
# between two rungs is the interpreter and the environment.
make_venv() {
  local python="$1" venv="$2" label="$3" with_cinderx="$4"
  [ -x "$python" ] || { warn "$label: interpreter missing, venv skipped"; return 0; }
  say "venv for $label"
  uv venv --python "$python" "$venv" >/dev/null
  local extras=(--extra c --extra dev)
  # CinderX comes from the lock like everything else, so the version in the
  # article is the version in the file rather than one a command line repeated.
  [ "$with_cinderx" = "1" ] && extras+=(--extra runtime)
  # UV_PROJECT_ENVIRONMENT and not VIRTUAL_ENV: uv ignores VIRTUAL_ENV when it
  # does not match the project's own .venv, and then syncs the project's instead --
  # silently, and destructively, since a sync removes what the extras do not ask for.
  (cd "$ROOT/service" && UV_PROJECT_ENVIRONMENT="$venv" \
      uv sync --frozen "${extras[@]}" >/dev/null)
  if [ "$with_cinderx" = "1" ]; then
    local got
    got="$("$venv/bin/python" -c "import importlib.metadata as m; print(m.version('cinderx'))")"
    info "cinderx $got"
    [ "$got" = "$CINDERX_VERSION" ] || warn "lock has cinderx $got, run.sh expects $CINDERX_VERSION"
    record "cinderx_version" "$got"
  fi
  info "$label: $("$venv/bin/python" -V)"
}

cmd_deps() {
  for v in STOCK TIER2 FORK; do
    local want="$BUILD/$(echo "$v" | tr 'A-Z' 'a-z')/bin/python3.14"
    local got; got="$(eval echo "\$${v}_PYTHON")"
    [ "$got" = "$want" ] || warn "$v interpreter overridden: $got (smoke test only)"
  done
  make_venv "$STOCK_PYTHON" "$VENV_STOCK" "stock" 1
  make_venv "$TIER2_PYTHON" "$VENV_TIER2" "tier2" 0
  make_venv "$FORK_PYTHON"  "$VENV_FORK"  "fork"  0
}

# ---------------------------------------------------------------------------
# probe
# ---------------------------------------------------------------------------

# What this build can actually do, asked of the build rather than assumed. A
# feature that is absent here is a rung that will be skipped, and knowing that
# before a six-hour campaign is worth one second of interrogation.
cmd_probe() {
  say "runtime capabilities"
  [ -x "$VENV_STOCK/bin/python" ] || die "no stock venv; run ./run.sh deps"
  "$VENV_STOCK/bin/python" - <<'PY'
import json, platform, sys
facts = {"python": sys.version, "platform": platform.platform()}
import cinderx
import cinderx.jit as jit
import importlib.metadata as md
facts["cinderx"] = md.version("cinderx")
for name in ("has_parallel_gc", "immortalize_heap", "enable_parallel_gc",
             "install_frame_evaluator", "_context"):
    facts[name] = hasattr(cinderx, name)
try:
    facts["parallel_gc_available"] = bool(cinderx.has_parallel_gc())
except Exception as exc:
    facts["parallel_gc_available"] = f"error: {exc}"
for name in ("auto", "force_compile", "precompile_all", "background_compile",
             "dump_elf", "load_aot_bundle", "get_and_clear_runtime_stats",
             "count_interpreted_calls"):
    facts[f"jit.{name}"] = hasattr(jit, name)
try:
    from cinderx.compiler.strict.loader import install    # noqa: F401
    facts["static_loader"] = True
except Exception as exc:
    facts["static_loader"] = f"error: {exc}"
width = max(len(k) for k in facts)
for k, v in facts.items():
    v = str(v).splitlines()[0][:70]
    print(f"   {k:<{width}}  {v}")
print()
if facts.get("parallel_gc_available") is not True:
    print("   ! parallel GC unavailable in this build: rung 09 will be skipped")
if not facts.get("jit.dump_elf"):
    print("   ! no AOT in this build: dump_elf/load_aot_bundle absent, b_jit_bulk")
    print("     will report the AOT legs as unavailable rather than fail")
PY
  record "probed" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

# ---------------------------------------------------------------------------
# dialect
# ---------------------------------------------------------------------------

# The Static Python reference: every accepted example must run and every rejected
# one must still be rejected. It exits non-zero when a snippet changed meaning,
# which is the only way a dialect note in the article can be trusted.
cmd_dialect() {
  say "Static Python dialect reference"
  [ -x "$VENV_STOCK/bin/python" ] || die "no stock venv; run ./run.sh deps"
  "$VENV_STOCK/bin/python" "$ROOT/dialect/run.py"
  "$VENV_STOCK/bin/python" "$ROOT/dialect/run.py" --markdown \
      > "$ROOT/dialect/REFERENCE.md"
  info "wrote dialect/REFERENCE.md"
}

# ---------------------------------------------------------------------------
# bench
# ---------------------------------------------------------------------------

# Three bench parameters must be a property of the process, never a loop inside
# one: a call cannot be un-made, immortalize_heap is irreversible, and auto() is
# a global policy. Hence the loops over separate invocations below.
# Two harnesses, so two helpers. pyb runs a pyperf bench and forwards BENCH_ARGS;
# fb runs one that records observations rather than timings and has its own
# argparser, which pyperf's flags would make it reject.
# One bench that dies must not cost the campaign, and must not pass unnoticed
# either: failures are collected and reported at the end, and the stage exits
# non-zero. A known example is b_framework under cinderx_jit, where auto()
# compiling the framework path segfaults on this platform.
BENCH_FAILED=()

pyb() {
  local config="$1" script="$2"; shift 2
  CX_BENCH_CONFIG="$config" "$BENCH_PY" "$ROOT/bench/$script" \
      "$@" ${BENCH_ARGS:+$BENCH_ARGS} \
    || { warn "$script [$config $*] failed with $?"; BENCH_FAILED+=("$script[$config $*]"); }
}

fb() {
  local config="$1" script="$2"; shift 2
  CX_BENCH_CONFIG="$config" "$BENCH_PY" "$ROOT/bench/$script" "$@" \
    || { warn "$script [$config $*] failed with $?"; BENCH_FAILED+=("$script[$config $*]"); }
}

# Three bench parameters must be a property of the process, never a loop inside
# one: a call cannot be un-made, immortalize_heap is irreversible, and auto() is
# a global policy. Hence the loops over separate invocations below.
cmd_bench() {
  say "microbenches"
  BENCH_PY="$VENV_STOCK/bin/python"
  [ -x "$BENCH_PY" ] || die "no stock venv; run ./run.sh deps"
  mkdir -p "$RESULTS"
  export BENCH_RESULTS_DIR="$RESULTS"

  for c in stock cinderx static cinderx_jit static_jit; do
    pyb "$c" b_ladder.py
  done

  for shape in attr index; do
    for n in 0 1 2 3 5 10 30; do
      pyb cinderx_jit b_jit_warmup.py --warmup-calls "$n" --shape "$shape"
    done
  done

  for c in static static_jit; do
    pyb "$c" b_prim_op.py
    pyb "$c" b_border.py
    fb  "$c" b_port_cost.py
  done

  for c in cinderx cinderx_jit; do
    pyb "$c" b_jit_deopt.py
    fb  "$c" b_jit_bulk.py
  done

  for c in cinderx cinderx_jit static static_jit; do
    for mode in auto forced; do
      fb "$c" b_jit_curve.py --jit-mode "$mode"
    done
  done

  for shape in chain gather sleep0; do
    for c in stock cinderx cinderx_jit; do
      pyb "$c" b_coro.py --shape "$shape"
    done
  done

  for c in stock cinderx cinderx_jit; do
    pyb "$c" b_framework.py
  done

  for v in visible frozen immortal; do
    pyb cinderx b_gc_collect.py --visibility "$v"
  done

  fb "" b_install_order.py
  fb cinderx b_cow.py

  # Lazy imports exist only in the fork, so this one runs on the fork's venv.
  if [ -x "$VENV_FORK/bin/python" ]; then
    info "lazy imports, on the fork"
    BENCH_PY="$VENV_FORK/bin/python" pyb "" b_lazy_imports.py
  else
    warn "lazy imports skipped: no fork venv"
  fi

  info "results in $RESULTS"
  if [ ${#BENCH_FAILED[@]} -gt 0 ]; then
    warn "${#BENCH_FAILED[@]} bench invocation(s) failed:"
    for f in "${BENCH_FAILED[@]}"; do warn "  $f"; done
    record "bench_failures" "${BENCH_FAILED[*]}"
    return 1
  fi
  record "bench_failures" "none"
}

# ---------------------------------------------------------------------------
# workshop
# ---------------------------------------------------------------------------

cmd_workshop() {
  say "workshop"
  local py="$VENV_STOCK/bin/python"
  [ -x "$py" ] || die "no stock venv; run ./run.sh deps"
  [ -n "${RECSYS_DB_HOST:-}" ] || die "set RECSYS_DB_HOST: the database goes on another host"
  have k6 || die "k6 is required for the ladder"

  # The fixture is seeded once. It is not re-seeded between rungs: the ladder
  # truncates impressions instead, which is cheaper and is the only part that
  # the service consumes.
  say "seeding the fixture"
  (cd "$ROOT/service" && PYTHONPATH=src "$py" -m recsys.infrastructure.seed \
      --items "${SEED_ITEMS:-100000}" --users "${SEED_USERS:-20000}" \
      --avg-degree "${SEED_DEGREE:-24}")
  (cd "$ROOT/service" && PYTHONPATH=src "$py" load/reset_fixture.py --stats) || true

  # The ladder takes one interpreter per invocation and skips rungs that need
  # another, so it is called once per build rather than once per campaign.
  say "ladder: rungs on stock plus CinderX"
  (cd "$ROOT/service" && "$py" load/ladder.py --run \
      --python "$py" --db-host "$RECSYS_DB_HOST" \
      --endpoints "${ENDPOINTS:-recommend,similar,events}" \
      --rates "${RATES:-200,400,800,1600,3200}" \
      --workers "${WORKERS:-$JOBS}" --out "$LADDER_OUT")

  if [ -x "$VENV_TIER2/bin/python" ]; then
    say "ladder: CPython's own JIT"
    (cd "$ROOT/service" && "$VENV_TIER2/bin/python" load/ladder.py --run \
        --python "$VENV_TIER2/bin/python" --db-host "$RECSYS_DB_HOST" \
        --available-images python-3.14-jit --only 02_stock_tier2 \
        --endpoints "${ENDPOINTS:-recommend,similar,events}" \
        --rates "${RATES:-200,400,800,1600,3200}" \
        --workers "${WORKERS:-$JOBS}" --out "$LADDER_OUT")
  else
    warn "tier2 rung skipped: no tier2 venv"
  fi

  if [ -x "$VENV_FORK/bin/python" ]; then
    say "ladder: the fork, and lazy imports"
    (cd "$ROOT/service" && "$VENV_FORK/bin/python" load/ladder.py --run \
        --python "$VENV_FORK/bin/python" --db-host "$RECSYS_DB_HOST" \
        --available-images meta-3.14 --only 03_fork,07_lazy_imports \
        --endpoints "${ENDPOINTS:-recommend,similar,events}" \
        --rates "${RATES:-200,400,800,1600,3200}" \
        --workers "${WORKERS:-$JOBS}" --out "$LADDER_OUT")
  else
    warn "fork rungs skipped: no fork venv"
  fi

  # Through HTTP at saturation the host dominates and the rungs blur, so the
  # kernel is also measured on its own, on the same graph and the same seeds.
  say "kernel matrix"
  for mode in off runtime jit; do
    (cd "$ROOT/service" && PYTHONPATH=src "$py" load/kernel_matrix.py \
        --mode "$mode" --users "${MATRIX_USERS:-40}")
  done
  info "verdicts in $LADDER_OUT"
}

# ---------------------------------------------------------------------------
# all, clean
# ---------------------------------------------------------------------------

cmd_all() {
  local started
  started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  stage check       cmd_check
  stage sources     cmd_sources
  stage interpreters cmd_interpreters
  stage deps        cmd_deps
  stage probe       cmd_probe
  stage dialect     cmd_dialect
  stage bench       cmd_bench
  stage workshop    cmd_workshop
  record "campaign_started" "$started"
  record "campaign_finished" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  say "done"
  info "manifest: $MANIFEST"
  info "bench results: $RESULTS"
  info "ladder verdicts: $LADDER_OUT"
}

# Sources and results survive: re-cloning 272 MB and re-running a campaign are
# not the same kind of cheap.
cmd_clean() {
  say "removing builds and venvs"
  rm -rf "$BUILD"
  info "kept: $WORK and $RESULTS"
}

# Print the header block: every comment line after the shebang, and stop at code.
usage() { awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "${BASH_SOURCE[0]}"; }

main() {
  local cmd="${1:-all}"
  case "$cmd" in
    check|sources|interpreters|deps|probe|dialect|bench|workshop|all|clean)
      "cmd_$cmd" ;;
    -h|--help|help) usage ;;
    *) usage; die "unknown subcommand: $cmd" ;;
  esac
}

main "$@"
