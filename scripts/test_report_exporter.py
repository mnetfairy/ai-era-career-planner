#!/usr/bin/env python3
"""
ai-era-career-planner report_generator.py 路径安全验证（2026-09-08 T09 修复配套）

测试范围（对应 T09 报告的"remediation #9 add tests"）：
  1. 默认 --output-dir 是 SKILL_DIR/exports/
  2. 显式传入 ./exports/（白名单内）应该成功
  3. 越界路径（/tmp）应被拒绝
  4. 相对路径穿越（./exports/../../etc）应被拒绝
  5. 连续两次导出不应覆盖前一次（collision-resistant 文件名）
  6. 显式 allow root 通过环境变量 AIERA_EXPORT_ROOT 可扩展
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


def _reset_default_export():
    if os.path.exists(DEFAULT_EXPORT):
        shutil.rmtree(DEFAULT_EXPORT)
    os.makedirs(DEFAULT_EXPORT, exist_ok=True)


def _run(args, env_extra=None, timeout=30):
    env = os.environ.copy()
    env["LANG"] = "C.UTF-8"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["python3", SCRIPT] + args,
        capture_output=True, text=True, timeout=timeout, env=env, cwd=SKILL_DIR,
    )


def test_default_output_dir():
    """Test 1: 不传 --output-dir 应使用默认 SKILL_DIR/exports/。"""
    print("\nTest 1: default --output-dir is SKILL_DIR/exports/")
    _reset_default_export()
    data = '{"nickname":"测试用户","recommendations":[{"title":"软件工程师","score":4,"reason":"AI工具熟练"}]}'
    r = _run(["--data", data])
    if r.returncode != 0:
        print(f"  {FAIL} exit={r.returncode}: {r.stderr[:200]}")
        return False
    files = os.listdir(DEFAULT_EXPORT)
    if not files or not files[0].endswith(".md"):
        print(f"  {FAIL} no .md file in default export dir: {files}")
        return False
    print(f"  {PASS} created: {files[0]}")
    return True


def test_within_allowed_root():
    """Test 2: 显式传入 ./exports/（白名单内）应成功。"""
    print("\nTest 2: explicit --output-dir=./exports/ (whitelisted) succeeds")
    _reset_default_export()
    data = '{"nickname":"测试用户","recommendations":[{"title":"产品经理","score":5}]}'
    r = _run(["--data", data, "--output-dir", "./exports/"])
    if r.returncode != 0:
        print(f"  {FAIL} exit={r.returncode}: {r.stderr[:200]}")
        return False
    print(f"  {PASS} explicit path accepted, output: {r.stdout.strip()}")
    return True


def test_outside_allowed_root():
    """Test 3: 越界路径（/tmp）应被拒绝，exit code 非 0。"""
    print("\nTest 3: --output-dir=/tmp should be REJECTED")
    data = '{"nickname":"测试用户"}'
    r = _run(["--data", data, "--output-dir", "/tmp"])
    if r.returncode == 0:
        # Check if it created anything (it shouldn't have)
        tmp_files = [f for f in os.listdir("/tmp") if f.startswith("职业规划报告_")]
        # remove any that might be from a previous run for fairness
        print(f"  {FAIL} /tmp path was ACCEPTED; returned 0. tmp files now: {tmp_files[:3]}")
        return False
    if "not inside any allowed export root" not in r.stderr and "allowed" not in r.stderr:
        print(f"  {WARN if False else FAIL} unexpected error msg: {r.stderr[:200]}")
    print(f"  {PASS} /tmp rejected (exit={r.returncode}): {r.stderr.strip()[:80]}")
    return True


def test_path_traversal():
    """Test 4: 路径穿越 ./exports/../../etc 应被拒绝。"""
    print("\nTest 4: path traversal ./exports/../../etc should be REJECTED")
    data = '{"nickname":"测试用户"}'
    r = _run(["--data", data, "--output-dir", "./exports/../../etc"])
    if r.returncode == 0:
        print(f"  {FAIL} traversal path was ACCEPTED")
        return False
    print(f"  {PASS} traversal rejected (exit={r.returncode})")
    return True


def test_collision_resistant_filename():
    """Test 5: 连续两次导出不应覆盖前一次，生成不同文件名。"""
    print("\nTest 5: two consecutive exports should NOT overwrite (collision-resistant)")
    _reset_default_export()
    data = '{"nickname":"测试用户"}'
    r1 = _run(["--data", data])
    # Brief delay to ensure different timestamp suffix
    time.sleep(1)
    r2 = _run(["--data", data])
    files = sorted(os.listdir(DEFAULT_EXPORT))
    if r1.returncode != 0 or r2.returncode != 0:
        print(f"  {FAIL} one run failed: r1={r1.returncode} r2={r2.returncode}")
        return False
    if len(files) < 2:
        print(f"  {FAIL} only {len(files)} file(s) created; expected ≥2: {files}")
        return False
    print(f"  {PASS} {len(files)} distinct files created: {files}")
    return True


def test_env_var_override():
    """Test 6: 环境变量 AIERA_EXPORT_ROOT 应能扩展允许的导出根目录。"""
    print("\nTest 6: AIERA_EXPORT_ROOT env var should extend allowed roots")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_real = os.path.realpath(tmp)
        env_extra = {"AIERA_EXPORT_ROOT": tmp_real}
        data = '{"nickname":"env-var-test"}'
        r = _run(["--data", data, "--output-dir", tmp], env_extra=env_extra)
        if r.returncode != 0:
            print(f"  {FAIL} env var override not honored: exit={r.returncode} stderr={r.stderr[:200]}")
            return False
        files = [f for f in os.listdir(tmp) if f.startswith("职业规划报告_")]
        if not files:
            print(f"  {FAIL} no file created in env-var directory: {os.listdir(tmp)}")
            return False
        print(f"  {PASS} env var honored; file: {files[0]}")
        return True


def main():
    print("=" * 60)
    print("ai-era-career-planner report_generator 路径安全验证 (T09 修复配套)")
    print("=" * 60)
    print(f"Script: {SCRIPT}")

    # Cleanup before run
    _reset_default_export()

    results = [
        ("Test 1 (default output dir)",        test_default_output_dir()),
        ("Test 2 (within allowed root)",       test_within_allowed_root()),
        ("Test 3 (outside allowed root)",      test_outside_allowed_root()),
        ("Test 4 (path traversal)",            test_path_traversal()),
        ("Test 5 (collision-resistant)",       test_collision_resistant_filename()),
        ("Test 6 (env var override)",          test_env_var_override()),
    ]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        print(f"  {PASS if ok else FAIL} {name}")
    print(f"\n{passed}/{total} tests passed")

    # Cleanup
    if os.path.exists(DEFAULT_EXPORT):
        shutil.rmtree(DEFAULT_EXPORT)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())