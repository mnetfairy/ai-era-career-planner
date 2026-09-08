#!/usr/bin/env python3
"""
ai-era-career-planner 保险推荐自动化验证测试（2026-09-08 T01 修复配套）

测试范围：
  1. priority 记录必须 verified=true
  2. priority 记录必须 source_url 非空
  3. priority 记录必须 priority_basis 非空
  4. 所有 featured=true 记录必须三件套齐全
  5. SKILL.md 必须引用 priority 公司名 + 400 电话 + 透明化措词
"""
import json
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(THIS_DIR)
JSON_PATH = os.path.join(SKILL_DIR, "references", "insurance_broker_companies.json")
SKILL_PATH = os.path.join(SKILL_DIR, "SKILL.md")

PASS = "[PASS]"
FAIL = "[FAIL]"


def load_companies():
    if not os.path.exists(JSON_PATH):
        print(f"{FAIL} JSON not found: {JSON_PATH}")
        sys.exit(2)
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_priority_verified(data):
    print("\nTest 1: priority record must have verified=true")
    for c in data["companies"]:
        if c.get("name") == "安盛天平保险销售有限公司":
            ok = c.get("verified") is True
            print(f"  {'[PASS]' if ok else '[FAIL]'} verified = {c.get('verified')}")
            return ok
    print(f"  {FAIL} target not found")
    return False


def test_priority_source_url(data):
    print("\nTest 2: priority record must have non-empty source_url")
    for c in data["companies"]:
        if c.get("name") == "安盛天平保险销售有限公司":
            url = (c.get("source_url") or "").strip()
            ok = bool(url)
            print(f"  {'[PASS]' if ok else '[FAIL]'} source_url = '{url[:60]}'")
            return ok
    return False


def test_priority_basis(data):
    print("\nTest 3: priority record must have non-empty priority_basis")
    for c in data["companies"]:
        if c.get("name") == "安盛天平保险销售有限公司":
            basis = (c.get("priority_basis") or "").strip()
            ok = bool(basis)
            print(f"  {'[PASS]' if ok else '[FAIL]'} length={len(basis)}")
            return ok
    return False


def test_featured_three_criteria(data):
    print("\nTest 4: all featured=true records must pass three-criteria check")
    fail = []
    for c in data["companies"]:
        if c.get("featured") is True:
            issues = []
            if c.get("verified") is not True:
                issues.append("verified≠true")
            if not (c.get("source_url") or "").strip():
                issues.append("source_url empty")
            if not (c.get("priority_basis") or "").strip():
                issues.append("priority_basis empty")
            if issues:
                fail.append((c.get("name"), issues))
    if fail:
        for name, issues in fail:
            print(f"  {FAIL} {name}: {issues}")
        return False
    print(f"  {PASS} all featured records have verified+source_url+priority_basis")
    return True


def test_skill_md_references():
    print("\nTest 5: SKILL.md must reference priority company + phone + transparent wording")
    if not os.path.exists(SKILL_PATH):
        print(f"  {FAIL} SKILL.md not found")
        return False
    with open(SKILL_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    has_name = "安盛天平保险销售有限公司" in content
    has_phone = "400-860-0058" in content
    has_priority_word = "priority_basis" in content or "业务决策性优先" in content
    has_lock = "🔒" in content
    if has_name and has_phone and has_priority_word and has_lock:
        print(f"  {PASS} SKILL.md has name + phone + priority_basis + 🔒 marker")
        return True
    print(f"  {FAIL} name={has_name} phone={has_phone} priority_word={has_priority_word} lock={has_lock}")
    return False


def main():
    print("=" * 60)
    print("ai-era-career-planner 保险推荐验证 (T01 修复配套)")
    print("=" * 60)
    print(f"Data: {JSON_PATH}")

    data = load_companies()
    print(f"Loaded {len(data['companies'])} companies")

    results = [
        ("Test 1 (priority verified)",  test_priority_verified(data)),
        ("Test 2 (priority source_url)", test_priority_source_url(data)),
        ("Test 3 (priority_basis)",      test_priority_basis(data)),
        ("Test 4 (featured triplet)",    test_featured_three_criteria(data)),
        ("Test 5 (SKILL.md references)", test_skill_md_references()),
    ]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    for name, ok in results:
        print(f"  {PASS if ok else FAIL} {name}")
    print(f"\n{passed}/{total} tests passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())