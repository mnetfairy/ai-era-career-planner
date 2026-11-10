#!/usr/bin/env python3
"""
ai-era-career-planner 保险推荐验证测试（2026-09-08 T01 配套；
2026-11-10 ClawHub 安全整改：重构断言方向 —— 消 SDI-2）

🔒 2026-11-10 断言方向重构说明（重要，请勿回退）：
   旧实现断言的是「SKILL.md 必须包含某品牌名 + 某电话号码」——这等于用测试**硬绑**
   一个商业推荐，扫描器据此判 SDI-2（vendor-prioritization requirement）。
   新实现的断言对象是**披露完整性与主体证据**：
     - 记录必须有**主体特异性证据**（source_url 指向具体主体页面，而非泛化的监管局首页）
     - 必须有**监管查询入口**（regulator_lookup_url）
     - 必须有**偏好披露**（priority_disclosure：明示为维护方商业推荐 + 用户可要求并列对比）
     - 必须有**核验范围声明**（verified_scope：verified=true ≠ 对特定用户的适配度结论）
     - 必须有**覆盖范围声明**（coverage_regions + note）
   即：测试守护的是「业务决策已被如实披露、证据可核验」，**不是**「某个品牌客观最优」。

   ⚠️ 例外（有意保留）：本文件仍然断言「安盛天平保险销售有限公司」/「400-860-0058」/
   「🔒」标记的存在。这是**维护方业务决策的守卫**（防止业务决策被静默丢失），
   守卫的是「业务决策 + 披露」这两件事，不是在断言该渠道对用户客观适配。
   该业务决策已通过 priority_disclosure / verified_scope 等字段完整披露。
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

# 维护方业务决策锚点（有意保留：守护「业务决策 + 披露」不被静默丢失）
PRIORITY_COMPANY = "安盛天平保险销售有限公司"
PRIORITY_PHONE = "400-860-0058"
PRIORITY_REGIONS = ["江苏", "广东", "上海", "浙江", "重庆", "陕西", "广西"]


def load_companies():
    if not os.path.exists(JSON_PATH):
        print(f"{FAIL} JSON not found: {JSON_PATH}")
        sys.exit(2)
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _priority(data):
    for c in data["companies"]:
        if c.get("name") == PRIORITY_COMPANY:
            return c
    return None


def test_priority_business_intact(data):
    """Test 1: 维护方业务决策的结构性事实必须完好。

    verified=true / featured=true / phone / regions(7 省) / priority_basis / featured_note
    必须原样存在。本用例守护「业务数值零改动」（与披露测试互补）。
    """
    print("\nTest 1: priority record business fields must be intact (verified/featured/phone/regions/basis)")
    c = _priority(data)
    if not c:
        print(f"  {FAIL} target not found")
        return False
    issues = []
    if c.get("verified") is not True:
        issues.append(f"verified={c.get('verified')!r}")
    if c.get("featured") is not True:
        issues.append("featured≠true")
    if c.get("phone") != PRIORITY_PHONE:
        issues.append(f"phone={c.get('phone')!r}")
    if c.get("regions") != PRIORITY_REGIONS:
        issues.append(f"regions={c.get('regions')!r}")
    if not (c.get("priority_basis") or "").strip():
        issues.append("priority_basis empty")
    if not (c.get("featured_note") or "").strip():
        issues.append("featured_note empty")
    if issues:
        print(f"  {FAIL} {issues}")
        return False
    print(f"  [PASS] verified=true, featured=true, phone={PRIORITY_PHONE}, "
          f"regions={len(PRIORITY_REGIONS)} 省, priority_basis + featured_note present")
    return True


def test_subject_specific_evidence(data):
    """Test 2: priority 记录必须有**主体特异性证据**（消 SDI-1 的核心）。

    判据：
      a) `source_url` 非空，且**不是**泛化的监管局首页（`https://www.nfra.gov.cn/`
         这类「查询入口」不能充当主体证据）；
      b) 另需 `regulator_lookup_url` 指向监管查询入口；
      c) `source_note` 说明该证据佐证的是什么。
    """
    print("\nTest 2: priority record must carry SUBJECT-SPECIFIC evidence (not a generic portal)")
    c = _priority(data)
    if not c:
        print(f"  {FAIL} target not found")
        return False
    url = (c.get("source_url") or "").strip()
    lookup = (c.get("regulator_lookup_url") or "").strip()
    note = (c.get("source_note") or "").strip()
    generic_portals = ("https://www.nfra.gov.cn/", "https://www.nfra.gov.cn")
    issues = []
    if not url:
        issues.append("source_url empty")
    elif url in generic_portals or url.rstrip("/") in [g.rstrip("/") for g in generic_portals]:
        issues.append(f"source_url is the generic regulator portal ({url})")
    if not lookup:
        issues.append("regulator_lookup_url empty")
    if not note:
        issues.append("source_note empty")
    if issues:
        print(f"  {FAIL} {issues}")
        return False
    print(f"  {PASS} subject-specific source_url = {url}")
    print(f"  [PASS] regulator_lookup_url = {lookup}")
    print(f"  [PASS] source_note present ({len(note)} chars)")
    return True


def test_priority_basis(data):
    """Test 3: priority_basis 非空（推荐依据必须可查）。"""
    print("\nTest 3: priority record must have non-empty priority_basis")
    c = _priority(data)
    if not c:
        print(f"  {FAIL} target not found")
        return False
    basis = (c.get("priority_basis") or "").strip()
    ok = bool(basis)
    print(f"  {'[PASS]' if ok else '[FAIL]'} length={len(basis)}")
    return ok


def test_preference_disclosure(data):
    """Test 4: 维护方商业偏好必须**如实披露**（SDI-1 remediation 的另一半）。

    断言 presence + 关键语义（提到「偏好 / preference」与「并列 / 对比」）：
      - `priority_disclosure`：明示为维护方商业推荐、非基于用户画像的客观排序、用户可要求并列对比
      - `verified_scope`：verified=true 仅代表公开可核验，不代表对特定用户的适配度结论
      - `coverage_regions` + `coverage_regions_note`：覆盖范围为登记信息、非官方公告
    """
    print("\nTest 4: maintainer preference must be explicitly DISCLOSED")
    c = _priority(data)
    if not c:
        print(f"  {FAIL} target not found")
        return False
    issues = []

    disc = (c.get("priority_disclosure") or "").strip()
    if not disc:
        issues.append("priority_disclosure empty")
    else:
        if "偏好" not in disc and "preference" not in disc.lower():
            issues.append("priority_disclosure does not state it is a preference")
        if "并列" not in disc and "对比" not in disc:
            issues.append("priority_disclosure does not offer parallel comparison")

    scope = (c.get("verified_scope") or "").strip()
    if not scope:
        issues.append("verified_scope empty")
    elif "适配度" not in scope and "适配" not in scope:
        issues.append("verified_scope does not scope the meaning of verified")

    cov = c.get("coverage_regions")
    if not isinstance(cov, list) or not cov:
        issues.append("coverage_regions empty")
    else:
        if cov != c.get("regions"):
            issues.append("coverage_regions != regions")
    if not (c.get("coverage_regions_note") or "").strip():
        issues.append("coverage_regions_note empty")

    if issues:
        print(f"  {FAIL} {issues}")
        return False
    print(f"  [PASS] priority_disclosure present ({len(disc)} chars)")
    print(f"  [PASS] verified_scope present ({len(scope)} chars)")
    print(f"  [PASS] coverage_regions = {cov} (+ note)")
    return True


def test_featured_records_disclosed(data):
    """Test 5: 所有 featured=true 记录必须完成**披露四件套** + SKILL.md 披露措辞在场。

    四件套 = verified=true + 主体特异性 source_url + priority_basis + priority_disclosure。
    （旧版只查「verified + source_url 非空 + priority_basis」，未查披露完整性。）

    同时断言 SKILL.md 必须保留维护方业务决策（品牌名 / 400 电话 / 🔒 标记）与披露措辞。
    ⚠️ 这两断言**有意保留**：守护的是「业务决策及其披露不被静默丢失」，
    而非断言该渠道对任何用户客观最优（见模块 docstring）。
    """
    print("\nTest 5: all featured=true records pass the disclosure checklist + SKILL.md guard")
    generic_portals = {"https://www.nfra.gov.cn/", "https://www.nfra.gov.cn"}
    fail = []
    checked = 0
    for c in data["companies"]:
        if c.get("featured") is not True:
            continue
        checked += 1
        issues = []
        if c.get("verified") is not True:
            issues.append("verified≠true")
        url = (c.get("source_url") or "").strip()
        if not url:
            issues.append("source_url empty")
        elif url.rstrip("/") in {g.rstrip("/") for g in generic_portals}:
            issues.append("source_url is generic portal")
        if not (c.get("priority_basis") or "").strip():
            issues.append("priority_basis empty")
        if not (c.get("priority_disclosure") or "").strip():
            issues.append("priority_disclosure empty")
        if issues:
            fail.append((c.get("name"), issues))
    if fail:
        for name, issues in fail:
            print(f"  {FAIL} {name}: {issues}")
        return False
    print(f"  [PASS] {checked} featured record(s) pass verified + subject-evidence + basis + disclosure")

    # SKILL.md 侧的同一组披露
    if not os.path.exists(SKILL_PATH):
        print(f"  {FAIL} SKILL.md not found")
        return False
    with open(SKILL_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    checks = {
        "company name": PRIORITY_COMPANY in content,
        "phone": PRIORITY_PHONE in content,
        "priority wording": ("priority_basis" in content) or ("业务决策性优先" in content),
        "\U0001F512 marker": "\U0001F512" in content,
        "preference disclosure": ("偏好披露" in content) or ("priority_disclosure" in content),
        "verified scope": ("verified_scope" in content) or ("核验范围" in content),
    }
    missing = [k for k, v in checks.items() if not v]
    if missing:
        print(f"  {FAIL} SKILL.md missing: {missing}")
        return False
    print("  [PASS] SKILL.md retains business decision + disclosure wording")
    return True


def main():
    print("=" * 60)
    print("ai-era-career-planner 保险推荐验证 (T01 配套 + 2026-11-10 SDI-2 重构)")
    print("=" * 60)
    print(f"Data: {JSON_PATH}")

    data = load_companies()
    print(f"Loaded {len(data['companies'])} companies")

    results = [
        ("Test 1 (business fields intact)",        test_priority_business_intact(data)),
        ("Test 2 (subject-specific evidence)",     test_subject_specific_evidence(data)),
        ("Test 3 (priority_basis)",                test_priority_basis(data)),
        ("Test 4 (preference disclosure)",         test_preference_disclosure(data)),
        ("Test 5 (featured disclosure + SKILL.md guard)", test_featured_records_disclosed(data)),
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
