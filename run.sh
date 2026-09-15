#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$ROOT/cinderx-workshop"
BUILD="$ROOT/build"
LOGS="$BUILD/logs"
MANIFEST="$BUILD/manifest.json"

CINDERX_VERSION="${CINDERX_VERSION:-2026.9.13.0}"

CPYTHON_SRC="${CPYTHON_SRC:-$WORK/cpython}"
CINDER_SRC="${CINDER_SRC:-$WORK/cinder}"
CINDERX_SRC="${CINDERX_SRC:-$WORK/cinderx}"

JOBS="${JOBS:-$( (nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4) )}"
PGO="${PGO:-1}"
KEEP_GOING="${KEEP_GOING:-0}"

STOCK="$BUILD/stock"
TIER2="$BUILD/tier2"
FORK="$BUILD/fork"

STOCK_PYTHON="${STOCK_PYTHON:-$STOCK/bin/python3.14}"
TIER2_PYTHON="${TIER2_PYTHON:-$TIER2/bin/python3.14}"
FORK_PYTHON="${FORK_PYTHON:-$FORK/bin/python3.14}"
VENV_STOCK="$BUILD/venv-stock"
VENV_TIER2="$BUILD/venv-tier2"
VENV_FORK="$BUILD/venv-fork"

BENCH_ARGS="${BENCH_ARGS:-}"

ENDPOINTS="${ENDPOINTS:-recommend,similar,events}"
RATES="${RATES:-recommend=25,45,80,140,250,420,700;similar=10,20,35,60,110,190,330,570;events=200,400,800,1400,2400,4000}"
STEP_SECONDS="${STEP_SECONDS:-30}"
DRAIN_SECONDS="${DRAIN_SECONDS:-10}"
WARMUP_SECONDS="${WARMUP_SECONDS:-60}"
WARMUP_RATE="${WARMUP_RATE:-25}"
LADDER_REPEATS="${LADDER_REPEATS:-1}"

RESULTS="${BENCH_RESULTS_DIR:-$ROOT/results}"
LADDER_OUT="$ROOT/service/load/results"

WQ_CPUMASK=/sys/devices/virtual/workqueue/cpumask
RESERVED="${CX_RESERVED_CPUS:-2-5}"
export CX_RESERVED_CPUS="$RESERVED"

COMPOSE_FILE="$ROOT/service/docker-compose.yml"
RECSYS_DB_PUBLISH_PORT="${RECSYS_DB_PUBLISH_PORT:-${RECSYS_DB_PORT:-55432}}"

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
info() { printf '   %s\n' "$*"; }
warn() { printf '\033[33m   ! %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31m   x %s\033[0m\n' "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

sysinfo() { PYTHONPATH="$ROOT" python3 -m bench.harness.system "$@"; }
budget() { sysinfo --cpu-budget "$1"; }
budget_count() {
  sysinfo --cpu-budget | awk -v k="$1" '$1 == k {print $3}'
}

on_cpus() {
  local cpus="$1"; shift
  if [ -n "$cpus" ] && have taskset; then
    taskset -c "$cpus" "$@"
  else
    "$@"
  fi
}

CURRENT_STAGE=""

stage() {
  local name="$1"; shift
  CURRENT_STAGE="$name"
  if [ "$KEEP_GOING" = "1" ]; then
    "$@" || warn "stage '$name' failed; continuing because KEEP_GOING=1"
  else
    "$@"
  fi
  CURRENT_STAGE=""
}

on_exit() {
  local rc=$?
  [ "$rc" = "0" ] && return 0
  [ -n "$CURRENT_STAGE" ] &&
    printf '\033[31m   x stage '"'"'%s'"'"' failed (exit %s)\033[0m\n' \
           "$CURRENT_STAGE" "$rc" >&2
  return 0
}
trap on_exit EXIT

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

is_root() { [ "$(id -u)" = "0" ]; }

GOVERNORS_GLOB="/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"
NO_TURBO="/sys/devices/system/cpu/intel_pstate/no_turbo"
BOOST="/sys/devices/system/cpu/cpufreq/boost"
PERF_RATE="/proc/sys/kernel/perf_event_max_sample_rate"
TUNE_BAK="${TUNE_BAK:-/var/tmp/cinderx-cpu-tune.bak}"

sysfs_write() {
  local value="$1" path="$2"
  if printf '%s\n' "$value" > "$path" 2>/dev/null; then
    return 0
  fi
  warn "could not write $value to $path"
  return 1
}

tune_remember() {
  local key="$1" value="$2"
  mkdir -p "$(dirname "$TUNE_BAK")"
  [ -f "$TUNE_BAK" ] && grep -q "^$key=" "$TUNE_BAK" && return 0
  printf '%s=%s\n' "$key" "$value" >> "$TUNE_BAK"
}

tune_recall() {
  local key="$1"
  [ -f "$TUNE_BAK" ] || return 1
  sed -n "s/^$key=//p" "$TUNE_BAK" | tail -1
}

tune_cpu() {
  is_linux || { warn "$(uname -s): no cpufreq knobs to set"; return 1; }
  if ! is_root; then
    warn "governor and turbo need root; leaving them as they are"
    warn "to set them: sudo $0 tune"
    return 1
  fi

  local touched=0 first=""
  for path in $GOVERNORS_GLOB; do
    [ -w "$path" ] || continue
    [ -n "$first" ] || { first="$(cat "$path")"; tune_remember governor "$first"; }
    sysfs_write performance "$path" && touched=1
  done
  if [ -n "$first" ]; then
    local now
    now="$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo unknown)"
    info "governor: $first -> $now (all CPUs)"
  else
    warn "no writable scaling_governor: cpufreq may not be exposed on this host"
  fi

  if [ -w "$NO_TURBO" ]; then
    tune_remember no_turbo "$(cat "$NO_TURBO")"
    sysfs_write 1 "$NO_TURBO" && { info "turbo: off (intel_pstate/no_turbo=1)"; touched=1; }
  elif [ -w "$BOOST" ]; then
    tune_remember boost "$(cat "$BOOST")"
    sysfs_write 0 "$BOOST" && { info "turbo: off (cpufreq/boost=0)"; touched=1; }
  else
    warn "no writable turbo knob: neither $NO_TURBO nor $BOOST"
  fi

  for path in /sys/devices/system/cpu/cpu*/cpufreq/scaling_min_freq; do
    [ -w "$path" ] || continue
    local top="${path%/scaling_min_freq}/cpuinfo_max_freq"
    [ -r "$top" ] && sysfs_write "$(cat "$top")" "$path" && touched=1
  done
  tune_remember min_freq floor
  info "scaling_min_freq: raised to each CPU's maximum"

  if [ -w "$PERF_RATE" ]; then
    tune_remember perf_rate "$(cat "$PERF_RATE")"
    sysfs_write 1 "$PERF_RATE" && { info "perf_event_max_sample_rate: 1"; touched=1; }
  fi

  tune_shield && touched=1
  tune_irqs && touched=1

  [ "$touched" = "1" ] && info "saved the previous values in $TUNE_BAK"
  [ "$touched" = "1" ]
}

tune_shield() {
  have systemctl || { warn "no systemctl: cannot shield the reserved CPUs"; return 1; }
  is_root || { warn "shielding the reserved CPUs needs root"; return 1; }
  local rest
  rest="$(sysinfo --host-cpus)" || return 1
  [ -n "$rest" ] || return 1
  local unit ok=0
  for unit in init.scope system.slice; do
    if systemctl set-property --runtime "$unit" "AllowedCPUs=$rest" 2>/dev/null; then
      ok=$((ok + 1))
    else
      warn "could not set AllowedCPUs on $unit"
    fi
  done
  [ "$ok" -gt 0 ] || return 1
  tune_remember shield "$ok"
  info "shield: daemons on $rest, cpu $RESERVED left to the measurement"
  local wq_mask
  if [ -w "$WQ_CPUMASK" ] && wq_mask="$(sysinfo --irq-mask)"; then
    tune_remember wq_cpumask "$(cat "$WQ_CPUMASK")"
    sysfs_write "$wq_mask" "$WQ_CPUMASK" &&
      info "unbound workqueues: on $rest as well"
  else
    warn "unbound workqueues: cannot write $WQ_CPUMASK, kworkers stay everywhere"
  fi
  info "user.slice is untouched: do not run anything else in this session"
}

untune_shield() {
  have systemctl || return 0
  [ -n "$(tune_recall shield || true)" ] || return 0
  local unit
  for unit in init.scope system.slice; do
    systemctl set-property --runtime "$unit" "AllowedCPUs=" 2>/dev/null || true
  done
  local wq_mask
  wq_mask="$(tune_recall wq_cpumask || true)"
  if [ -n "$wq_mask" ] && [ -w "$WQ_CPUMASK" ]; then
    sysfs_write "$wq_mask" "$WQ_CPUMASK" &&
      info "unbound workqueues: back to $wq_mask"
  fi
  info "shield: every CPU back to every slice"
}

tune_irqs() {
  local isolated mask
  isolated="$RESERVED"
  if [ -z "$isolated" ]; then
    warn "no reserved CPUs: IRQ affinity left alone (set CX_RESERVED_CPUS)"
    return 1
  fi
  if have systemctl && systemctl is-active --quiet irqbalance 2>/dev/null; then
    systemctl stop irqbalance && tune_remember irqbalance active
    info "irqbalance: stopped"
  fi
  mask="$(sysinfo --irq-mask)" || return 1
  [ -n "$mask" ] || return 1
  tune_remember irq_default "$(cat /proc/irq/default_smp_affinity 2>/dev/null || true)"
  sysfs_write "$mask" /proc/irq/default_smp_affinity || true
  local moved=0 pinned=0
  for path in /proc/irq/[0-9]*/smp_affinity; do
    [ -w "$path" ] || continue
    if printf '%s\n' "$mask" > "$path" 2>/dev/null; then moved=$((moved + 1)); else pinned=$((pinned + 1)); fi
  done
  info "IRQ affinity: $moved moved off cpu $isolated, $pinned are per-CPU and stayed"
  return 0
}

untune_cpu() {
  is_linux || die "$(uname -s): no cpufreq knobs to restore"
  is_root  || die "restoring the governor and turbo needs root: sudo $0 untune"
  [ -f "$TUNE_BAK" ] || die "no record in $TUNE_BAK: nothing was tuned by this script"

  local governor no_turbo boost
  governor="$(tune_recall governor || true)"
  if [ -n "$governor" ]; then
    for path in $GOVERNORS_GLOB; do
      [ -w "$path" ] && sysfs_write "$governor" "$path"
    done
    info "governor: back to $governor"
  fi
  no_turbo="$(tune_recall no_turbo || true)"
  boost="$(tune_recall boost || true)"
  if [ -n "$no_turbo" ] && [ -w "$NO_TURBO" ]; then
    sysfs_write "$no_turbo" "$NO_TURBO" && info "turbo: back to no_turbo=$no_turbo"
  elif [ -n "$boost" ] && [ -w "$BOOST" ]; then
    sysfs_write "$boost" "$BOOST" && info "turbo: back to boost=$boost"
  fi

  if [ -n "$(tune_recall min_freq || true)" ]; then
    for path in /sys/devices/system/cpu/cpu*/cpufreq/scaling_min_freq; do
      [ -w "$path" ] || continue
      local bottom="${path%/scaling_min_freq}/cpuinfo_min_freq"
      [ -r "$bottom" ] && sysfs_write "$(cat "$bottom")" "$path"
    done
    info "scaling_min_freq: back to each CPU's minimum"
  fi

  local perf_rate irq_default
  perf_rate="$(tune_recall perf_rate || true)"
  if [ -n "$perf_rate" ] && [ -w "$PERF_RATE" ]; then
    sysfs_write "$perf_rate" "$PERF_RATE" && info "perf_event_max_sample_rate: back to $perf_rate"
  fi

  irq_default="$(tune_recall irq_default || true)"
  if [ -n "$irq_default" ]; then
    local all=""
    all="$(sysinfo --irq-mask-all)" || all=""
    sysfs_write "$irq_default" /proc/irq/default_smp_affinity || true
    if [ -n "$all" ]; then
      for path in /proc/irq/[0-9]*/smp_affinity; do
        [ -w "$path" ] && printf '%s\n' "$all" > "$path" 2>/dev/null || true
      done
      info "IRQ affinity: back to every CPU"
    fi
  fi
  if [ -n "$(tune_recall irqbalance || true)" ] && have systemctl; then
    systemctl start irqbalance && info "irqbalance: started"
  fi
  rm -f "$TUNE_BAK"
}

cmd_tune() {
  say "tuning the host"
  tune_cpu || true
  say "measurement preconditions"
  sysinfo 2>&1 | sed 's/^/   /' || true
}

cmd_untune() {
  say "restoring the host"
  untune_shield
  untune_cpu
}

cmd_check() {
  say "host preconditions"
  local missing=()
  for tool in make python3; do
    have "$tool" || missing+=("$tool")
  done
  have cc || have gcc || have clang || missing+=("a C compiler")
  have uv || missing+=("uv (https://docs.astral.sh/uv/)")
  have k6 || missing+=("k6 (the workshop's load generator)")
  [ ${#missing[@]} -eq 0 ] || die "missing: ${missing[*]}"
  info "tools: make cc uv k6 present"

  if ! is_linux; then
    warn "$(uname -s), not Linux. The fork, lazy imports, the parallel collector,"
    warn "AOT loading, smaps and perf are Linux-only; those stages will be skipped"
    warn "and the campaign will be incomplete. Publishable runs need Linux."
  fi

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

  say "cpu budget"
  sysinfo --cpu-budget | while read -r who cpus n; do
    info "$(printf '%-9s %-12s %s core(s)' "$who" "$cpus" "$n")"
  done

  say "measurement preconditions"
  tune_cpu || true
  local pre
  pre="$(sysinfo 2>&1 || true)"
  printf '%s\n' "$pre" | sed 's/^/   /'
  if ! printf '%s' "$pre" | grep -qi "preflight: ok"; then
    warn "the host is not tuned for measurement; see the complaints above"
    warn "benches will still run, but CX_BENCH_STRICT=1 will refuse them"
  fi

  if [ -z "${RECSYS_DB_HOST:-}" ] && ! have docker; then
    warn "RECSYS_DB_HOST is unset and docker is absent: the workshop cannot run"
  elif [ -z "${RECSYS_DB_HOST:-}" ] || db_is_local; then
    info "database: local, through compose, on 127.0.0.1:${RECSYS_DB_PUBLISH_PORT}"
    warn "a local database still shares caches, memory bandwidth and the disk"
    warn "with the service: set RECSYS_DB_HOST elsewhere for a publishable run"
  else
    info "database host: ${RECSYS_DB_HOST}"
  fi
}

tree_sha256() {
  local dir="$1"
  [ -d "$dir" ] || { echo "unknown"; return 0; }
  find "$dir" -type f \
       -not -path '*/.git/*' -not -path '*/__pycache__/*' \
       -not -name '*.pyc' -not -name '*.o' -not -name '*.so' \
       -print0 \
    | LC_ALL=C sort -z \
    | xargs -0 sha256sum 2>/dev/null \
    | sed "s| $dir/| |" \
    | sha256sum \
    | cut -d" " -f1
}

use_source() {
  local name="$1" dest="$2" var="$3"
  [ -d "$dest" ] || die "$name: no source tree at $dest; nothing is downloaded, so put the tree there or set $var"
  local digest
  digest="$(tree_sha256 "$dest")"
  record "${name}_path" "$dest"
  record "${name}_tree_sha256" "$digest"
  info "$name: $dest"
  info "$name tree sha256: $digest"
}

tree_version() {
  sed -n 's/^#define PY_VERSION *"\(.*\)".*/\1/p' "$1/Include/patchlevel.h" 2>/dev/null
}

cmd_sources() {
  say "local source trees; nothing is downloaded"
  use_source cpython "$CPYTHON_SRC" CPYTHON_SRC
  use_source cinder  "$CINDER_SRC"  CINDER_SRC
  use_source cinderx "$CINDERX_SRC" CINDERX_SRC

  local sv fv
  sv="$(tree_version "$CPYTHON_SRC")"
  fv="$(tree_version "$CINDER_SRC")"
  record "cpython_tree_version" "${sv:-unknown}"
  record "cinder_tree_version" "${fv:-unknown}"
  info "baseline ${sv:-unknown}, fork ${fv:-unknown}"
}

build_python() {
  local src="$1" prefix="$2" label="$3" extra="${4:-}"
  if [ -x "$prefix/bin/python3.14" ]; then
    info "$label: already built at $prefix"
    return 0
  fi
  [ -d "$src" ] || die "$label: source tree $src is missing; it has to be there already, nothing is downloaded"
  say "building $label"
  mkdir -p "$LOGS"
  local log="$LOGS/build-$label.log"

  local tools=()
  if have clang && have clang++; then
    tools=(CC=clang CXX=clang++)
    have llvm-profdata && tools+=("LLVM_PROFDATA=$(command -v llvm-profdata)")
    have llvm-ar && tools+=("LLVM_AR=$(command -v llvm-ar)")
    info "compiler: $(clang --version | head -1)"
  else
    warn "clang absent: building $label with the default compiler"
    warn "the extension is built with clang, so this mixes two compilers"
  fi

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
    env "${tools[@]}" ./configure --prefix="$prefix" "${opt[@]}" ${extra:+$extra}
    make -j"$JOBS"
    make install
  ) >"$log" 2>&1 || { tail -30 "$log"; die "$label: build failed, see $log"; }
  "$prefix/bin/python3.14" -VV | sed 's/^/   /'
  record "${label}_version" "$("$prefix/bin/python3.14" -VV | tr '\n' ' ')"
  record "${label}_compiler" "$("$prefix/bin/python3.14" -c \
      'import sysconfig; print(sysconfig.get_config_var("CC"))')"
}

cmd_interpreters() {
  build_python "$CPYTHON_SRC" "$STOCK" "stock"
  build_python "$CPYTHON_SRC" "$TIER2" "tier2" "--enable-experimental-jit"
  if is_linux; then
    build_python "$CINDER_SRC" "$FORK" "fork"
  else
    warn "fork build skipped: not Linux"
  fi
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

make_venv() {
  local python="$1" venv="$2" label="$3" with_cinderx="$4"
  [ -x "$python" ] || { warn "$label: interpreter missing, venv skipped"; return 0; }
  say "venv for $label"
  uv venv --clear --python "$python" "$venv" >/dev/null
  local extras=(--extra c --extra dev)
  (cd "$ROOT/service" && UV_PROJECT_ENVIRONMENT="$venv" \
      uv sync --frozen "${extras[@]}" >/dev/null)
  if [ "$with_cinderx" = "1" ]; then
    [ -d "$CINDERX_SRC" ] || die "cinderx source missing at $CINDERX_SRC; it has to be there already, nothing is downloaded"
    say "building cinderx from $CINDERX_SRC"
    mkdir -p "$LOGS"
    local cxlog="$LOGS/build-cinderx.log"
    local env=()

    if have clang && have clang++; then
      env+=(CC=clang CXX=clang++)
      info "compiler: clang ($(clang --version | head -1 | grep -o 'version [0-9.]*'))"
    else
      warn "clang absent: building with the default compiler"
      warn "gcc 13.3 is known to ICE on cinderx/Jit/code_patcher.cpp"
    fi

    local pyver
    pyver="$("$venv/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    if [ "$pyver" != "3.12" ]; then
      env+=(ENABLE_EVAL_HOOK=0 ENABLE_GENERATOR_AWAITER=0)
      warn "python $pyver: eval hook and generator awaiter off, they are 3.12-only"
    fi

    rm -rf "$CINDERX_SRC/scratch"
    env "${env[@]}" uv pip install --python "$venv/bin/python" "$CINDERX_SRC" \
        >"$cxlog" 2>&1 \
      || { grep -i -m 10 "error" "$cxlog" | sed 's/^/   /'; die "cinderx: build failed, see $cxlog"; }
    local got
    got="$("$venv/bin/python" -c "import importlib.metadata as m; print(m.version('cinderx'))")"
    info "cinderx $got, from the tree"
    [ "$got" = "$CINDERX_VERSION" ] || warn "the tree builds cinderx $got, run.sh expects $CINDERX_VERSION"
    record "cinderx_version" "$got"
  fi
  info "$label: $("$venv/bin/python" -V)"
}

cmd_deps() {
  for v in STOCK TIER2 FORK; do
    local want="$BUILD/$(echo "$v" | tr 'A-Z' 'a-z')/bin/python3.14"
    local var="${v}_PYTHON"
    local got="${!var}"
    [ "$got" = "$want" ] || warn "$v interpreter overridden: $got (smoke test only)"
  done
  make_venv "$STOCK_PYTHON" "$VENV_STOCK" "stock" 0
  make_venv "$TIER2_PYTHON" "$VENV_TIER2" "tier2" 0
  make_venv "$FORK_PYTHON"  "$VENV_FORK"  "fork"  1
}

cmd_probe() {
  say "runtime capabilities"
  [ -x "$VENV_FORK/bin/python" ] || die "no fork venv; run ./run.sh deps"
  "$VENV_FORK/bin/python" - <<'PY'
import platform, sys
facts = {"python": sys.version, "platform": platform.platform()}
import cinderx
import cinderx.jit as jit
import importlib.metadata as md
facts["cinderx"] = md.version("cinderx")
for name in ("has_parallel_gc", "immortalize_heap", "enable_parallel_gc",
             "install_frame_evaluator"):
    facts[name] = hasattr(cinderx, name)
try:
    facts["parallel_gc_available"] = bool(cinderx.has_parallel_gc())
except Exception as exc:
    facts["parallel_gc_available"] = f"error: {exc}"
import cinderjit
for name in ("auto", "force_compile", "precompile_all", "dump_elf",
             "load_aot_bundle", "get_and_clear_runtime_stats",
             "count_interpreted_calls"):
    here = hasattr(cinderjit, name)
    facts[f"jit.{name}"] = here if hasattr(jit, name) == here else f"{here} (cinderjit only)"
try:
    from cinderx.compiler.strict.loader import install
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
if not str(facts.get("jit.dump_elf", "")).startswith("True"):
    print("   ! no AOT in this build: dump_elf/load_aot_bundle absent, b_jit_bulk")
    print("     will report the AOT legs as unavailable rather than fail")
PY
  record "probed" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

cmd_dialect() {
  say "Static Python dialect reference"
  [ -x "$VENV_FORK/bin/python" ] || die "no fork venv: Static Python needs cinderx; run ./run.sh deps"
  "$VENV_FORK/bin/python" "$ROOT/dialect/run.py"
  "$VENV_FORK/bin/python" "$ROOT/dialect/run.py" --markdown \
      > "$ROOT/dialect/REFERENCE.md"
  info "wrote dialect/REFERENCE.md"
}

BENCH_FAILED=()

py_for() {
  if [ "$1" = "stock" ]; then echo "$VENV_STOCK/bin/python"; else echo "$VENV_FORK/bin/python"; fi
}

pyb() {
  local config="$1" script="$2"; shift 2
  local BENCH_PY="${BENCH_PY:-$(py_for "$config")}"
  CX_BENCH_CONFIG="$config" "$BENCH_PY" "$ROOT/bench/$script/main.py" \
      "$@" ${BENCH_ARGS:+$BENCH_ARGS} \
    || { warn "$script [$config $*] failed with $?"; BENCH_FAILED+=("$script[$config $*]"); }
}

fb() {
  local config="$1" script="$2"; shift 2
  local BENCH_PY="${BENCH_PY:-$(py_for "$config")}"
  CX_BENCH_CONFIG="$config" "$BENCH_PY" "$ROOT/bench/$script/main.py" "$@" \
    || { warn "$script [$config $*] failed with $?"; BENCH_FAILED+=("$script[$config $*]"); }
}

cmd_bench() {
  say "microbenches"
  [ -x "$VENV_STOCK/bin/python" ] || die "no stock venv; run ./run.sh deps"
  [ -x "$VENV_FORK/bin/python" ] || die "no fork venv: cinderx lives there; run ./run.sh deps"
  mkdir -p "$RESULTS"
  export BENCH_RESULTS_DIR="$RESULTS"

  for c in stock cinderx static cinderx_jit static_jit; do
    pyb "$c" b_ladder
  done

  for shape in attr index; do
    for n in 0 1 2 3 5 10 30; do
      pyb cinderx_jit b_jit_warmup --warmup-calls "$n" --shape "$shape" \
          --label "$shape-w$n"
    done
  done

  for c in static static_jit; do
    pyb "$c" b_prim_op
    pyb "$c" b_border
    fb  "$c" b_port_cost
  done

  for c in cinderx cinderx_jit; do
    pyb "$c" b_jit_deopt
    fb  "$c" b_jit_bulk
  done

  for c in cinderx cinderx_jit static static_jit; do
    for mode in auto forced; do
      fb "$c" b_jit_curve --jit-mode "$mode"
    done
  done

  for c in stock cinderx cinderx_jit; do
    pyb "$c" b_framework
  done

  for c in stock cinderx cinderx_jit static static_jit; do
    pyb "$c" b_attr
  done

  for v in visible frozen immortal; do
    pyb cinderx b_gc_collect --visibility "$v" --label "$v"
  done

  fb "" b_install_order
  fb cinderx b_cow

  pyb "" b_lazy_imports

  info "results in $RESULTS"
  if [ ${#BENCH_FAILED[@]} -gt 0 ]; then
    warn "${#BENCH_FAILED[@]} bench invocation(s) failed:"
    for f in "${BENCH_FAILED[@]}"; do warn "  $f"; done
    record "bench_failures" "${BENCH_FAILED[*]}"
    return 1
  fi
  record "bench_failures" "none"
}

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

db_is_local() {
  case "${RECSYS_DB_HOST:-}" in
    localhost|127.0.0.1|::1|0.0.0.0) return 0 ;;
    *) return 1 ;;
  esac
}

db_container_running() {
  [ -n "$(compose ps --quiet --status running db 2>/dev/null)" ]
}

port_taken() {
  have ss || return 1
  ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]$1\$"
}

cmd_db() {
  local action="${1:-up}"
  have docker || die "docker is required for the local database; or set RECSYS_DB_HOST"
  docker compose version >/dev/null 2>&1 || die "docker compose v2 or newer is required"

  case "$action" in
    up)
      say "local database"
      export RECSYS_DB_CPUSET="${RECSYS_DB_CPUSET:-$(budget db)}"
      export RECSYS_DB_PUBLISH_PORT
      if ! db_container_running && port_taken "$RECSYS_DB_PUBLISH_PORT"; then
        die "port $RECSYS_DB_PUBLISH_PORT is already in use: set RECSYS_DB_PUBLISH_PORT"
      fi
      info "cpuset: $RECSYS_DB_CPUSET"
      info "port: 127.0.0.1:$RECSYS_DB_PUBLISH_PORT -> 5432 in the container"
      compose up -d --wait --wait-timeout 180 db \
        || die "the database did not come up healthy; compose logs db"
      info "up: $(compose ps --format '{{.Name}} {{.Status}}' db)"
      ;;
    down)
      say "stopping the local database"
      compose down
      info "kept: the pgdata volume, so the fixture survives; ./run.sh db reset drops it"
      ;;
    reset)
      say "dropping the local database and its data"
      warn "this deletes the seeded fixture; the next workshop run reseeds from scratch"
      compose down --volumes
      ;;
    status)
      say "local database"
      compose ps db
      ;;
    *) die "unknown db action: $action (up, down, reset, status)" ;;
  esac
}

db_prepare() {
  if [ -z "${RECSYS_DB_HOST:-}" ]; then
    have docker || die "set RECSYS_DB_HOST: the database goes on another host"
    warn "RECSYS_DB_HOST is unset: using the local database from compose"
    warn "it shares caches, memory bandwidth and the disk with the service"
    RECSYS_DB_HOST=127.0.0.1
  fi
  export RECSYS_DB_HOST
  if db_is_local; then
    export RECSYS_DB_PORT="$RECSYS_DB_PUBLISH_PORT"
    cmd_db up
    record "db_placement" "local-compose ${RECSYS_DB_HOST}:${RECSYS_DB_PORT} cpuset=${RECSYS_DB_CPUSET}"
  else
    record "db_placement" "remote ${RECSYS_DB_HOST}:${RECSYS_DB_PORT:-5432}"
  fi
}

cmd_workshop() {
  say "workshop"
  local py="$VENV_STOCK/bin/python"
  [ -x "$py" ] || die "no stock venv; run ./run.sh deps"
  have k6 || die "k6 is required for the ladder"
  have taskset || warn "taskset is absent: the cpu budget below cannot be enforced"

  export RECSYS_SERVICE_CPUSET="${RECSYS_SERVICE_CPUSET:-$(budget service)}"
  export RECSYS_LOAD_CPUSET="${RECSYS_LOAD_CPUSET:-$(budget load)}"
  local workers="${WORKERS:-$(budget_count service)}"
  info "cpus: service=${RECSYS_SERVICE_CPUSET:-unpinned} generator=${RECSYS_LOAD_CPUSET:-unpinned}"
  info "workers: $workers"
  record "workshop_cpus" "service=${RECSYS_SERVICE_CPUSET} load=${RECSYS_LOAD_CPUSET} workers=$workers"

  db_prepare

  say "seeding the fixture"
  (cd "$ROOT/service" && PYTHONPATH=src on_cpus "$RECSYS_LOAD_CPUSET" "$py" \
      -m recsys.infrastructure.seed \
      --items "${SEED_ITEMS:-100000}" --users "${SEED_USERS:-20000}" \
      --avg-degree "${SEED_DEGREE:-24}")
  local fixture
  fixture="$(cd "$ROOT/service" && PYTHONPATH=src on_cpus "$RECSYS_LOAD_CPUSET" \
      "$py" load/reset_fixture.py --stats)"
  printf '%s\n' "$fixture"
  record "fixture_at_start" "$(printf '%s' "$fixture" | tr '\n' ' ')"

  say "ladder: the stock baseline"
  (cd "$ROOT/service" && "$py" load/ladder.py --run \
      --python "$py" --db-host "$RECSYS_DB_HOST" \
      --available-images stock-3.14 --only 01_stock \
      --endpoints "$ENDPOINTS" --rates "$RATES" \
      --step-seconds "$STEP_SECONDS" --drain-seconds "$DRAIN_SECONDS" \
      --warmup-seconds "$WARMUP_SECONDS" --warmup-rate "$WARMUP_RATE" \
      --repeats "$LADDER_REPEATS" \
      --workers "$workers" --out "$LADDER_OUT")

  if [ -x "$VENV_TIER2/bin/python" ]; then
    say "ladder: CPython's own JIT"
    (cd "$ROOT/service" && "$VENV_TIER2/bin/python" load/ladder.py --run \
        --python "$VENV_TIER2/bin/python" --db-host "$RECSYS_DB_HOST" \
        --available-images python-3.14-jit --only 02_stock_tier2 \
        --endpoints "$ENDPOINTS" --rates "$RATES" --no-repeat-first \
        --step-seconds "$STEP_SECONDS" --drain-seconds "$DRAIN_SECONDS" \
        --warmup-seconds "$WARMUP_SECONDS" --warmup-rate "$WARMUP_RATE" \
        --repeats "$LADDER_REPEATS" \
        --workers "$workers" --out "$LADDER_OUT")
  else
    warn "tier2 rung skipped: no tier2 venv"
  fi

  if [ -x "$VENV_FORK/bin/python" ]; then
    say "ladder: the fork and every CinderX rung"
    (cd "$ROOT/service" && "$VENV_FORK/bin/python" load/ladder.py --run \
        --python "$VENV_FORK/bin/python" --db-host "$RECSYS_DB_HOST" \
        --available-images meta-3.14 \
        --only 03_fork,04_runtime,05_jit,06_jit_precompiled,07_lazy_imports,08_immortalized,09_parallel_gc,10_static_kernel_nojit,11_static_kernel,12_static_embeddings \
        --endpoints "$ENDPOINTS" --rates "$RATES" \
        --step-seconds "$STEP_SECONDS" --drain-seconds "$DRAIN_SECONDS" \
        --warmup-seconds "$WARMUP_SECONDS" --warmup-rate "$WARMUP_RATE" \
        --repeats "$LADDER_REPEATS" \
        --workers "$workers" --out "$LADDER_OUT")
  else
    warn "fork rungs skipped: no fork venv"
  fi

  say "kernel matrix"
  for mode in off runtime jit; do
    local matrix_py="$py"
    if [ "$mode" != "off" ]; then
      matrix_py="$VENV_FORK/bin/python"
      [ -x "$matrix_py" ] || { warn "kernel matrix $mode skipped: no fork venv"; continue; }
    fi
    (cd "$ROOT/service" && PYTHONPATH=src on_cpus "$RECSYS_SERVICE_CPUSET" "$matrix_py" \
        load/kernel_matrix.py --mode "$mode" --users "${MATRIX_USERS:-40}")
  done

  say "embeddings matrix"
  for mode in off runtime jit; do
    local emb_py="$py"
    if [ "$mode" != "off" ]; then
      emb_py="$VENV_FORK/bin/python"
      [ -x "$emb_py" ] || { warn "embeddings matrix $mode skipped: no fork venv"; continue; }
    fi
    (cd "$ROOT/service" && PYTHONPATH=src on_cpus "$RECSYS_SERVICE_CPUSET" "$emb_py" \
        load/embeddings_matrix.py --mode "$mode" \
        --items "${MATRIX_ITEMS:-3}" --reps "${MATRIX_REPS:-3}")
  done
  info "verdicts in $LADDER_OUT"
}

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

cmd_clean() {
  say "removing builds and venvs"
  rm -rf "$BUILD"
  info "kept: the source trees and $RESULTS"
  if have docker && db_container_running; then
    info "kept: the local database, still up; ./run.sh db down stops it"
  fi
}

usage() {
  cat <<'TXT'
Build the interpreters, install the dependencies, run the benches and the workshop.

  ./run.sh check         host preconditions; refuses a host that cannot measure
  ./run.sh tune          governor, turbo, cpu shield, IRQs; needs root
  ./run.sh untune        put all of them back the way they were
  ./run.sh sources       check the local CPython, Meta fork and CinderX trees
  ./run.sh interpreters  build all three, with identical flags
  ./run.sh deps          one venv per interpreter, CinderX into the fork's
  ./run.sh probe         report what this build can actually do, before measuring
  ./run.sh dialect       verify the Static Python reference and emit REFERENCE.md
  ./run.sh bench         the microbenches, through pyperf
  ./run.sh db up|down    a local Postgres through compose; reset also drops its data
  ./run.sh workshop      seed the fixture, then the ladder and the kernel matrix
  ./run.sh all           every stage above, in order
  ./run.sh clean         drop builds and venvs; sources and results are kept

Nothing is downloaded. The CPython, Meta fork and CinderX trees have to be on
disk already, under cinderx-workshop/ by default.

Tune once as root, then run the campaign as yourself:

  sudo ./run.sh tune && ./run.sh all

The database and the load generator belong on another host: set RECSYS_DB_HOST.
Without it the workshop starts a local Postgres from service/docker-compose.yml
and says so; then all three tenants share this host and ./run.sh check prints
which cores each one gets.

  CX_RESERVED_CPUS   cores kept for the thing being measured (default 2-5)
  CX_BENCH_CPUS      pin one run to an explicit set instead
  BENCH_ARGS         passed to every bench, e.g. --processes 1 --values 2
  KEEP_GOING=1       do not stop at the first stage that fails
  PGO=0              build without PGO and LTO
  CPYTHON_SRC        local CPython tree      (default cinderx-workshop/cpython)
  CINDER_SRC         local Meta fork tree    (default cinderx-workshop/cinder)
  CINDERX_SRC        local CinderX tree      (default cinderx-workshop/cinderx)
TXT
}

main() {
  local cmd="${1:-all}"
  if is_root && [ "$cmd" != "tune" ] && [ "$cmd" != "untune" ]; then
    warn "running as root: builds, venvs and results will be owned by root"
    warn "root is only needed for the knobs: sudo $0 tune, then $0 $cmd as yourself"
  fi
  case "$cmd" in
    check|tune|untune|sources|interpreters|deps|probe|dialect|bench|workshop|all|clean)
      "cmd_$cmd" ;;
    db) shift; cmd_db "$@" ;;
    -h|--help|help) usage ;;
    *) usage; die "unknown subcommand: $cmd" ;;
  esac
}

main "$@"
