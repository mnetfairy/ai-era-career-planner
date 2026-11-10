#!/usr/bin/env python3
"""
ai-era-career-planner report_generator.py 路径安全验证（T09 修复配套；
2026-10-26 ClawHub 复审加固；2026-11-10 ClawHub 安全整改：导出根收敛到 ./exports/）

⚠️ 本测试只使用临时目录，绝不删除 SKILL_DIR/exports 下的任何文件。
   所有导出产物都写入 tempfile.mkdtemp() 建立的临时目录（并通过 AIERA_EXPORT_ROOT
   注入为允许根），shutil.rmtree 只作用于这些临时目录，且使用 ignore_errors=True。
   测试结束时会断言 SKILL_DIR/exports 的内容与运行前完全一致（只读比对）。

🔒 2026-11-10 整改要点（导出根语义反转）：
   旧语义：AIERA_EXPORT_ROOT 可把**任意**目录追加为允许根（测试 6 / 11 断言"成功"）。
   新语义：允许根集合 = {./exports/}；AIERA_EXPORT_ROOT **只能追加 ./exports/ 之内
   的子目录**。因此：
     - Test 6  → 反转为「env 指向 ./exports/ 外部 → 必须被拒绝」
     - Test 6b → 新增「env 指向 ./exports/ 内部子目录 → 必须成功」
     - Test 11 → 反转为「plain abs dir（默认导出根之外）→ 必须被拒绝」
   其余 10 个用例（越界拒绝 / 路径穿越拒绝 / symlink 拒绝 ×3 / 不覆盖 / NUL / 默认根）
   断言不变。

🔒 环境变量处理（2026-11-10，消 E2「Env Variable Harvesting」）：
   旧实现 `env = os.environ.copy()` 会**枚举并复制全部环境变量**（可能夹带凭据）。
   新实现只给**最小白名单**：PATH / HOME / LANG / PYTHONPATH（+ 用例显式传入的
   AIERA_EXPORT_ROOT）。不复制、不枚举、不打印任何其他环境变量。

测试范围：
  1. 默认 --output-dir 是 SKILL_DIR/exports/（通过「脚本副本 + 临时 skill 根」验证，
     真实 SKILL_DIR/exports 全程只读）
  2. 显式传入白名单内路径应该成功
  3. 越界路径应被拒绝
  4. 相对路径穿越（..）应被拒绝
  5. 连续两次导出不应覆盖前一次（collision-resistant 文件名）
  6. [2026-11-10 反转] AIERA_EXPORT_ROOT 指向 ./exports/ **外部** → 必须被拒绝
  6b.[2026-11-10 新增] AIERA_EXPORT_ROOT 指向 ./exports/ **内部子目录** → 必须成功
  7. --output-dir 本身是指向 /tmp 的 symlink → 必须被拒绝
  8. 父目录链中任一级是 symlink → 必须被拒绝
  9. 允许根（AIERA_EXPORT_ROOT）本身是 symlink → 必须被拒绝，
     且文件**没有**写到 symlink 的目标目录
 10. 默认 exports/ 目录被替换成 symlink → 必须被拒绝，
     且文件**没有**写到 skill 目录之外
 11. [2026-11-10 反转] 用户显式指定普通真实绝对目录（在 ./exports/ 之外）→ 必须被拒绝
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(THIS_DIR)
SCRIPT = os.path.join(SKILL_DIR, "scripts", "report_generator.py")
DEFAULT_EXPORT = os.path.join(SKILL_DIR, "exports")

PASS = "[PASS]"
FAIL = "[FAIL]"

# 🔒 2026-11-10：传给子进程的**最小白名单环境变量**。
# 不再使用 os.environ.copy()（消 E2：Env Variable Harvesting）。
MIN_ENV_KEYS = ("PATH", "HOME", "LANG", "PYTHONPATH")

# 真实导出目录的初始快照（只读比对，测试绝不写入/删除它）
_INITIAL_EXPORT_SNAPSHOT = None


def _minimal_env(extra=None):
    """构造最小白名单环境：只保留 PATH / HOME / LANG / PYTHONPATH + 显式传入项。"""
    env = {}
    for key in MIN_ENV_KEYS:
        val = os.environ.get(key)
        if val is not None:
            env[key] = val
    env.setdefault("LANG", "C.UTF-8")
    if extra:
        env.update(extra)
    return env


def _snapshot(path):
    """只读快照：返回 {相对路径: (size, mtime_ns)}；目录不存在则返回 None。"""
    if not os.path.isdir(path):
        return None
    snap = {}
    for root, _dirs, files in os.walk(path):
        for name in files:
            full = os.path.join(root, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            snap[os.path.relpath(full, path)] = (st.st_size, st.st_mtime_ns)
    return snap


def _run(script, args, env_extra=None, timeout=30):
    env = _minimal_env(env_extra)
    return subprocess.run(
        ["python3", script] + args,
        capture_output=True, text=True, timeout=timeout, env=env, cwd=SKILL_DIR,
    )


def _make_fake_skill(tmp_root):
    """在临时目录里复制一份 report_generator.py，构造「假的 skill 根」。

    脚本用 SKILL_DIR = dirname(dirname(__file__)) 推导默认导出根，因此把脚本放到
    <tmp>/fake_skill/scripts/ 下，其默认导出根就变成 <tmp>/fake_skill/exports/
    ——测试可以在临时目录里验证「默认路径」行为，而完全不触碰真实的
    SKILL_DIR/exports。
    """
    fake_skill = os.path.join(tmp_root, "fake_skill")
    fake_scripts = os.path.join(fake_skill, "scripts")
    os.makedirs(fake_scripts, exist_ok=True)
    fake_script = os.path.join(fake_scripts, "report_generator.py")
    shutil.copy2(SCRIPT, fake_script)
    return fake_skill, fake_script


def _module_default_export_root():
    """只读方式读取真实脚本的 DEFAULT_EXPORT_ROOT 常量（不执行其 __main__）。

    实现方式：subprocess 调用脚本的 `--print-default-export-root` 只读自省参数。
    **不用动态模块加载** —— 动态执行会被 ClawHub 静态分析器判为
    `suspicious.dynamic_code_execution`（critical）。
    """
    r = subprocess.run(
        ["python3", SCRIPT, "--print-default-export-root"],
        capture_output=True, text=True, timeout=30, cwd=SKILL_DIR,
        env=_minimal_env(),
    )
    if r.returncode != 0:
        raise RuntimeError(f"self-introspection failed: exit={r.returncode}: {r.stderr[:200]}")
    lines = [ln.strip() for ln in r.stdout.strip().splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("self-introspection returned empty output")
    return lines[-1]


def test_default_output_dir():
    """Test 1: 不传 --output-dir 应使用默认 SKILL_DIR/exports/。

    实现方式：在临时目录里放一份脚本副本，默认根随之变成临时路径；
    同时只读断言真实脚本的 DEFAULT_EXPORT_ROOT 常量确实是 SKILL_DIR/exports。
    """
    print("\nTest 1: default --output-dir is SKILL_DIR/exports/")
    try:
        real_default = _module_default_export_root()
    except Exception as e:  # noqa: BLE001
        print(f"  {FAIL} cannot read DEFAULT_EXPORT_ROOT: {e}")
        return False
    if os.path.realpath(real_default or "") != os.path.realpath(DEFAULT_EXPORT):
        print(f"  {FAIL} DEFAULT_EXPORT_ROOT={real_default} != {DEFAULT_EXPORT}")
        return False
    print(f"  [PASS] DEFAULT_EXPORT_ROOT == {DEFAULT_EXPORT} (read-only check)")

    with tempfile.TemporaryDirectory() as tmp:
        fake_skill, fake_script = _make_fake_skill(tmp)
        data = '{"nickname":"测试用户","recommendations":[{"title":"软件工程师","score":4,"reason":"AI工具熟练"}]}'
        r = _run(fake_script, ["--data", data])
        if r.returncode != 0:
            print(f"  {FAIL} exit={r.returncode}: {r.stderr[:200]}")
            return False
        fake_export = os.path.join(fake_skill, "exports")
        files = sorted(os.listdir(fake_export)) if os.path.isdir(fake_export) else []
        if not files or not files[0].endswith(".md"):
            print(f"  {FAIL} no .md file in default export dir: {files}")
            return False
        print(f"  {PASS} default export root created (in temp dir): {files[0]}")
        return True


def test_within_allowed_root():
    """Test 2: 显式传入默认导出根（白名单内）应成功。"""
    print("\nTest 2: explicit --output-dir=<default export root> (whitelisted) succeeds")
    with tempfile.TemporaryDirectory() as tmp:
        fake_skill, fake_script = _make_fake_skill(tmp)
        data = '{"nickname":"测试用户","recommendations":[{"title":"产品经理","score":5}]}'
        r = _run(fake_script, ["--data", data, "--output-dir", os.path.join(fake_skill, "exports")])
        if r.returncode != 0:
            print(f"  {FAIL} exit={r.returncode}: {r.stderr[:200]}")
            return False
        print(f"  {PASS} explicit path accepted, output: {r.stdout.strip()}")
        return True


def test_outside_allowed_root():
    """Test 3: 越界路径（允许根之外的临时目录）应被拒绝，exit code 非 0。"""
    print("\nTest 3: --output-dir outside allowed roots should be REJECTED")
    with tempfile.TemporaryDirectory() as tmp_out, tempfile.TemporaryDirectory() as tmp_home:
        fake_skill, fake_script = _make_fake_skill(tmp_home)
        data = '{"nickname":"测试用户"}'
        r = _run(fake_script, ["--data", data, "--output-dir", os.path.realpath(tmp_out)])
        if r.returncode == 0:
            print(f"  {FAIL} out-of-root path was ACCEPTED; stdout={r.stdout[:200]}")
            return False
        print(f"  {PASS} rejected (exit={r.returncode}): {r.stderr.strip()[:120]}")
        return True


def test_path_traversal():
    """Test 4: 路径穿越（../..）应被拒绝。"""
    print("\nTest 4: path traversal ../.. should be REJECTED")
    with tempfile.TemporaryDirectory() as tmp:
        fake_skill, fake_script = _make_fake_skill(tmp)
        data = '{"nickname":"测试用户"}'
        r = _run(fake_script, ["--data", data, "--output-dir", "./exports/../../etc"])
        if r.returncode == 0:
            print(f"  {FAIL} traversal path was ACCEPTED")
            return False
        print(f"  {PASS} traversal rejected (exit={r.returncode}): {r.stderr.strip()[:120]}")
        return True


def test_collision_resistant_filename():
    """Test 5: 连续两次导出不应覆盖前一次，生成不同文件名。"""
    print("\nTest 5: two consecutive exports should NOT overwrite (collision-resistant)")
    with tempfile.TemporaryDirectory() as tmp:
        fake_skill, fake_script = _make_fake_skill(tmp)
        out_dir = os.path.join(fake_skill, "exports")
        data = '{"nickname":"测试用户"}'
        r1 = _run(fake_script, ["--data", data, "--output-dir", out_dir])
        time.sleep(1)  # 确保时间戳后缀不同
        r2 = _run(fake_script, ["--data", data, "--output-dir", out_dir])
        files = sorted(os.listdir(out_dir)) if os.path.isdir(out_dir) else []
        if r1.returncode != 0 or r2.returncode != 0:
            print(f"  {FAIL} one run failed: r1={r1.returncode} r2={r2.returncode}")
            return False
        if len(files) < 2:
            print(f"  {FAIL} only {len(files)} file(s) created; expected >=2: {files}")
            return False
        print(f"  {PASS} {len(files)} distinct files created: {files}")
        return True


def test_env_var_outside_root_rejected():
    """Test 6 [2026-11-10 反转]: AIERA_EXPORT_ROOT 指向 ./exports/ **外部** → 必须被拒绝。

    旧语义（2026-10-28）：env 扩展允许根 → 成功。
    新语义（2026-11-10 整改，消 SDI-3 / TP4）：AIERA_EXPORT_ROOT 只能追加
    ./exports/ 之内的子目录 → 指向外部目录时**被丢弃**（记 WARNING），
    该目录不在允许根内 → 命令被拒绝，且**不得**在该目录产生任何报告文件。
    """
    print("\nTest 6 [reversed]: AIERA_EXPORT_ROOT pointing OUTSIDE ./exports/ -> must be REJECTED")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_real = os.path.realpath(tmp)
        fake_skill, fake_script = _make_fake_skill(tmp)
        env_extra = {"AIERA_EXPORT_ROOT": tmp_real}
        data = '{"nickname":"env-var-outside"}'
        r = _run(fake_script, ["--data", data, "--output-dir", tmp_real], env_extra=env_extra)
        if r.returncode == 0:
            print(f"  {FAIL} out-of-root env var was ACCEPTED; stdout={r.stdout[:200]}")
            return False
        leaked = [f for f in os.listdir(tmp_real) if f.startswith("职业规划报告_")]
        if leaked:
            print(f"  {FAIL} report was written outside the export root: {leaked}")
            return False
        print(f"  {PASS} out-of-root env var rejected (exit={r.returncode}); "
              f"nothing written to {tmp_real}")
        print(f"         stderr: {r.stderr.strip()[:160]}")
        return True


def test_env_var_subdir_allowed():
    """Test 6b [2026-11-10 新增]: AIERA_EXPORT_ROOT 指向 ./exports/ **内部子目录** → 必须成功。

    这是收紧后**仍然可用**的正常用法：用户在 ./exports/ 下开一个自己的子目录
    （如 ./exports/tracking/），通过 env 指定 → 允许根集合追加该子目录 → 写入成功。
    """
    print("\nTest 6b [new]: AIERA_EXPORT_ROOT pointing INSIDE ./exports/ -> must SUCCEED")
    with tempfile.TemporaryDirectory() as tmp:
        fake_skill, fake_script = _make_fake_skill(tmp)
        subdir = os.path.join(fake_skill, "exports", "tracking")
        os.makedirs(subdir, exist_ok=True)
        env_extra = {"AIERA_EXPORT_ROOT": subdir}
        data = '{"nickname":"env-var-subdir"}'
        r = _run(fake_script, ["--data", data, "--output-dir", subdir], env_extra=env_extra)
        if r.returncode != 0:
            print(f"  {FAIL} in-root env subdir was REJECTED: exit={r.returncode} "
                  f"stderr={r.stderr[:200]}")
            return False
        files = [f for f in os.listdir(subdir) if f.startswith("职业规划报告_")]
        if not files:
            print(f"  {FAIL} no report produced in the env subdir: {os.listdir(subdir)}")
            return False
        print(f"  {PASS} in-root env subdir accepted; file: {files[0]}")
        return True


def test_output_dir_is_symlink():
    """Test 7: --output-dir 本身是指向 /tmp 的 symlink → 必须被拒绝。

    这是 2026-10-26 加固的核心回归：旧实现先 resolve() 再查 is_symlink()，
    resolve() 已经跟随了符号链接，检查永远为 False（本用例在旧实现下会 PASSED
    地写出文件）。
    """
    print("\nTest 7: --output-dir is a symlink pointing to /tmp -> must be REJECTED")
    with tempfile.TemporaryDirectory() as tmp:
        link = os.path.join(tmp, "link_to_tmp")
        try:
            os.symlink("/tmp", link)
        except (OSError, NotImplementedError) as e:
            print(f"  {FAIL} cannot create symlink on this platform: {e}")
            return False
        if not os.path.islink(link):
            print(f"  {FAIL} symlink was not created")
            return False
        fake_skill, fake_script = _make_fake_skill(tmp)
        env_extra = {"AIERA_EXPORT_ROOT": os.path.realpath(tmp)}
        data = '{"nickname":"symlink-test"}'
        r = _run(fake_script, ["--data", data, "--output-dir", link], env_extra=env_extra)
        if r.returncode == 0:
            print(f"  {FAIL} symlink output-dir was ACCEPTED; stdout={r.stdout[:200]}")
            return False
        if "symlink" not in r.stderr.lower():
            print(f"  {FAIL} rejected but not by the symlink guard: {r.stderr.strip()[:200]}")
            return False
        print(f"  {PASS} symlink output-dir rejected (exit={r.returncode}): {r.stderr.strip()[:120]}")
        return True


def test_parent_chain_symlink():
    """Test 8: 父目录链中任一级是 symlink → 必须被拒绝。"""
    print("\nTest 8: a symlink anywhere in the parent chain -> must be REJECTED")
    with tempfile.TemporaryDirectory() as tmp:
        real_sub = os.path.join(tmp, "real_sub")
        os.makedirs(real_sub, exist_ok=True)
        link_sub = os.path.join(tmp, "link_sub")
        try:
            os.symlink(real_sub, link_sub)
        except (OSError, NotImplementedError) as e:
            print(f"  {FAIL} cannot create symlink on this platform: {e}")
            return False
        target = os.path.join(link_sub, "sub_out")
        fake_skill, fake_script = _make_fake_skill(tmp)
        env_extra = {"AIERA_EXPORT_ROOT": os.path.realpath(tmp)}
        data = '{"nickname":"parent-symlink-test"}'
        r = _run(fake_script, ["--data", data, "--output-dir", target], env_extra=env_extra)
        if r.returncode == 0:
            print(f"  {FAIL} parent-chain symlink was ACCEPTED; stdout={r.stdout[:200]}")
            return False
        if "symlink" not in r.stderr.lower():
            print(f"  {FAIL} rejected but not by the symlink guard: {r.stderr.strip()[:200]}")
            return False
        print(f"  {PASS} parent-chain symlink rejected (exit={r.returncode}): {r.stderr.strip()[:120]}")
        return True


def test_allowed_root_is_symlink():
    """Test 9: 允许根（AIERA_EXPORT_ROOT）本身是 symlink → 必须被拒绝。

    2026-10-27 加固（ClawHub 第二轮 P0）：旧实现把允许根的「字面路径」当作
    豁免锚点，允许根本身是 symlink 时整条链的 symlink 检查被跳过，文件会写到
    symlink 目标目录（允许根之外）。本用例断言：
      a) 命令被拒绝（exit != 0）
      b) symlink 的目标目录里**没有**产生任何报告文件
    """
    print("\nTest 9: allowed root itself is a symlink -> must be REJECTED (no write to target)")
    with tempfile.TemporaryDirectory() as tmp:
        real_root = os.path.join(tmp, "real_root")
        os.makedirs(real_root, exist_ok=True)
        root_link = os.path.join(tmp, "root_link")
        try:
            os.symlink(real_root, root_link)
        except (OSError, NotImplementedError) as e:
            print(f"  {FAIL} cannot create symlink on this platform: {e}")
            return False
        out_dir = os.path.join(root_link, "sub")
        os.makedirs(out_dir, exist_ok=True)
        fake_skill, fake_script = _make_fake_skill(tmp)
        env_extra = {"AIERA_EXPORT_ROOT": root_link}
        data = '{"nickname":"allowed-root-symlink"}'
        r = _run(fake_script, ["--data", data, "--output-dir", out_dir], env_extra=env_extra)
        if r.returncode == 0:
            print(f"  {FAIL} symlink allowed root was ACCEPTED; stdout={r.stdout[:200]}")
            return False
        # 关键断言：文件没有写到 symlink 目标目录
        leaked = []
        for root, _dirs, files in os.walk(real_root):
            for name in files:
                if name.endswith(".md"):
                    leaked.append(os.path.join(root, name))
        if leaked:
            print(f"  {FAIL} report was written to the symlink target dir: {leaked}")
            return False
        print(f"  {PASS} symlink allowed root rejected (exit={r.returncode}); "
              f"nothing written to target dir")
        return True


def test_default_exports_is_symlink():
    """Test 10: 默认 exports/ 目录被替换成 symlink → 必须被拒绝。

    2026-10-27 加固（ClawHub 第二轮 P0）：默认导出根（SKILL_DIR/exports/）
    走与 AIERA_EXPORT_ROOT 完全相同的检查路径——是 symlink 就不可用于授权。
    本用例在**临时目录**里造一个假 skill 根（脚本副本），把它的 exports/ 换成
    symlink，断言命令被拒绝，且文件没有写到 skill 目录之外。
    """
    print("\nTest 10: default exports/ dir is a symlink -> must be REJECTED (no write outside skill)")
    with tempfile.TemporaryDirectory() as tmp:
        fake_skill, fake_script = _make_fake_skill(tmp)
        real_exports = os.path.join(tmp, "real_exports")
        os.makedirs(real_exports, exist_ok=True)
        exports_link = os.path.join(fake_skill, "exports")
        try:
            os.symlink(real_exports, exports_link)
        except (OSError, NotImplementedError) as e:
            print(f"  {FAIL} cannot create symlink on this platform: {e}")
            return False
        data = '{"nickname":"default-exports-symlink"}'
        r = _run(fake_script, ["--data", data])
        if r.returncode == 0:
            print(f"  {FAIL} symlinked default exports was ACCEPTED; stdout={r.stdout[:200]}")
            return False
        # 关键断言：没有文件写到 symlink 目标目录（skill 目录之外）
        leaked = [f for f in os.listdir(real_exports) if f.endswith(".md")]
        if leaked:
            print(f"  {FAIL} report was written outside the skill dir: {leaked}")
            return False
        print(f"  {PASS} symlinked default exports rejected (exit={r.returncode}); "
              f"nothing written outside the skill dir")
        return True


def test_plain_absolute_dir_rejected():
    """Test 11 [2026-11-10 反转]: 用户显式指定普通真实绝对目录（在 ./exports/ 之外）→ 必须被拒绝。

    旧语义（2026-10-28）：plain abs dir → 成功（防「修过头」）。
    新语义（2026-11-10 整改）：允许根唯一（./exports/）→ 任何外部绝对目录
    都在边界之外 → 必须被拒绝。这正是 SDI-3 / TP4 的整改目标：
    manifest 声明只允许写 ./exports/，代码就不能写到别处。
    """
    print("\nTest 11 [reversed]: explicit plain real absolute dir OUTSIDE ./exports/ -> must be REJECTED")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_real = os.path.realpath(tmp)
        fake_skill, fake_script = _make_fake_skill(tmp)
        env_extra = {"AIERA_EXPORT_ROOT": tmp_real}
        data = '{"nickname":"plain-dir-now-rejected"}'
        r = _run(fake_script, ["--data", data, "--output-dir", tmp_real], env_extra=env_extra)
        if r.returncode == 0:
            print(f"  {FAIL} plain absolute dir outside ./exports/ was ACCEPTED; "
                  f"stdout={r.stdout[:200]}")
            return False
        leaked = [f for f in os.listdir(tmp_real) if f.startswith("职业规划报告_")]
        if leaked:
            print(f"  {FAIL} report was written to the plain dir: {leaked}")
            return False
        print(f"  {PASS} plain absolute dir rejected (exit={r.returncode}): "
              f"{r.stderr.strip()[:120]}")
        return True


def main():
    global _INITIAL_EXPORT_SNAPSHOT
    _INITIAL_EXPORT_SNAPSHOT = _snapshot(DEFAULT_EXPORT)

    print("=" * 60)
    print("ai-era-career-planner report_generator 路径安全验证 (T09 + 2026-10-26 + 2026-11-10 整改)")
    print("=" * 60)
    print(f"Script: {SCRIPT}")
    print(f"注意：只使用临时目录，绝不删除 {DEFAULT_EXPORT} 下的任何文件")
    print(f"子进程环境变量：最小白名单 {MIN_ENV_KEYS}（不复制 os.environ）")

    results = [
        ("Test 1 (default output dir)",      test_default_output_dir()),
        ("Test 2 (within allowed root)",     test_within_allowed_root()),
        ("Test 3 (outside allowed root)",    test_outside_allowed_root()),
        ("Test 4 (path traversal)",          test_path_traversal()),
        ("Test 5 (collision-resistant)",     test_collision_resistant_filename()),
        ("Test 6 (env var outside -> reject)", test_env_var_outside_root_rejected()),
        ("Test 6b (env var subdir -> allow)", test_env_var_subdir_allowed()),
        ("Test 7 (output-dir is symlink)",   test_output_dir_is_symlink()),
        ("Test 8 (parent chain symlink)",    test_parent_chain_symlink()),
        ("Test 9 (allowed root is symlink)", test_allowed_root_is_symlink()),
        ("Test 10 (default exports symlink)", test_default_exports_is_symlink()),
        ("Test 11 (plain abs dir -> reject)", test_plain_absolute_dir_rejected()),
    ]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        print(f"  {PASS if ok else FAIL} {name}")
    print(f"\n{passed}/{total} tests passed")

    # 只读自证：真实导出目录与运行前完全一致
    final_snapshot = _snapshot(DEFAULT_EXPORT)
    unchanged = final_snapshot == _INITIAL_EXPORT_SNAPSHOT
    print(f"\n  {PASS if unchanged else FAIL} real exports dir unchanged: "
          f"{DEFAULT_EXPORT} (before={_INITIAL_EXPORT_SNAPSHOT}, after={final_snapshot})")

    return 0 if (passed == total and unchanged) else 1


if __name__ == "__main__":
    sys.exit(main())
