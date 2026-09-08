#!/usr/bin/env python3
"""
职业规划报告生成器（2026-09-08 T09 安全加固）

变更要点：
  1. --output-dir 必须位于 ALLOWED_EXPORT_ROOTS 之内（默认 ./exports/；可由环境变量
     AIERA_EXPORT_ROOT 追加；不允许任意路径）。
  2. 解析后的路径若包含符号链接直接拒绝。
  3. 使用独占创建模式（mode='x'），同一天多次导出生成 collision-resistant 文件名而非
     覆盖旧文件——保证不静默覆盖已有导出。
  4. 拒绝绝对路径越界、相对路径穿越（..）、NUL 字节等异常输入。
  5. 显式以 0600 权限写入（仅宿主用户可读写）。

调用方式：
  python3 scripts/report_generator.py --data '<json>' --output-dir ./exports
  python3 scripts/report_generator.py --data '<json>'   # 默认输出到 SKILL_DIR/exports/
"""
import json
import os
import secrets
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(THIS_DIR)
DEFAULT_EXPORT_ROOT = os.path.join(SKILL_DIR, "exports")
ALLOWED_EXPORT_ROOTS_ENV = "AIERA_EXPORT_ROOT"  # 可选追加允许的导出根目录（绝对路径列表，:分隔）


def _load_allowed_roots():
    """读取允许的导出根目录集合。默认 DEFAULT_EXPORT_ROOT，可由环境变量追加。"""
    roots = {os.path.realpath(DEFAULT_EXPORT_ROOT)}
    env_val = os.environ.get(ALLOWED_EXPORT_ROOTS_ENV, "").strip()
    if env_val:
        for p in env_val.split(":"):
            p = p.strip()
            if p:
                roots.add(os.path.realpath(p))
    return roots


def _validate_output_dir(output_dir_arg, allowed_roots):
    """验证 --output-dir 在 ALLOWED_EXPORT_ROOTS 之内；拒绝越界/符号链接/穿越。"""
    if not output_dir_arg or not isinstance(output_dir_arg, str):
        raise ValueError("output-dir must be a non-empty string")
    if "\x00" in output_dir_arg:
        raise ValueError("output-dir contains NUL byte")

    # Resolve to absolute canonical path (without following terminal symlink)
    requested = Path(output_dir_arg).resolve(strict=False)

    # Reject if any parent of requested is a symlink (escape attempt)
    for parent in [requested] + list(requested.parents):
        try:
            if parent.is_symlink():
                raise ValueError(f"output-dir path traverses a symlink: {parent}")
        except OSError:
            pass

    real = os.path.realpath(str(requested))
    for allowed in allowed_roots:
        try:
            if os.path.commonpath([real, allowed]) == allowed:
                return Path(real)
        except ValueError:
            # Different drives on Windows; not a containment match.
            continue
    raise ValueError(
        f"output-dir is not inside any allowed export root. "
        f"Requested (resolved): {real}; allowed: {sorted(allowed_roots)}"
    )


def _generate_collision_resistant_name(date_str):
    """collision-resistant 文件名：职业规划报告_YYYYMMDD_HHMMSS_<8hex>.md
    同一秒多次导出也基本不会冲突；不再使用固定文件名避免覆盖。"""
    time_str = datetime.now().strftime("%H%M%S")
    suffix = secrets.token_hex(4)  # 8 hex chars = 32 bits entropy
    return f"职业规划报告_{date_str}_{time_str}_{suffix}.md"


def build_recs(recs):
    lines = []
    star = chr(9733)
    for i, r in enumerate(recs, 1):
        lines.append("### {0}. 【{1}】 适合指数：{2}".format(
            i, r.get('title', '方向' + str(i)), star * r.get('score', 3)))
        for k, v in [('推荐理由', r.get('reason', '')),
                      ('AI评级', r.get('ai_rating', '')),
                      ('薪资参考', r.get('salary', '')),
                      ('入门路径', r.get('path', '')),
                      ('3年预期', r.get('expectation', '')),
                      ('潜在风险', r.get('risk', ''))]:
            if v:
                lines.append("- **{0}**：{1}".format(k, v))
        lines.append('')
    return '\n'.join(lines)


def generate_report(data):
    today = datetime.now().strftime('%Y-%m-%d')
    ai = data.get('ai_guide', {})
    acts = data.get('actions', {})
    recs_md = build_recs(data.get('recommendations', []))
    md = [
        '# 个性化职业规划报告',
        '',
        '> 生成日期：' + today,
        '',
        '---',
        '',
        '## 基础档案',
        '',
        '- 昵称：' + data.get('nickname', '未提供'),
        '- 当前阶段：' + data.get('stage', '未提供'),
        '- 霍兰德代码：' + data.get('holland', '未测评'),
        '- MBTI类型：' + data.get('mbti', '未测评'),
        '- 职业锚：' + data.get('anchor', '未测评'),
        '- 核心价值观：' + data.get('values', '未明确'),
        '- 城市：' + data.get('city', '未提供'),
        '',
        '---',
        '',
        '## 职业方向推荐',
        '',
        recs_md,
        '',
        '## AI时代生存指南',
        '',
        '- 核心技能：' + ai.get('skills', '详见推荐职业'),
        '- 必学AI工具：' + ai.get('tools', '暂无'),
        '- 建议认证：' + ai.get('cert', '暂无'),
        '',
        '## 下一步行动清单',
        '',
        '- 今天：' + acts.get('today', '暂无'),
        '- 1个月内：' + acts.get('1month', '暂无'),
        '- 3个月内：' + acts.get('3months', '暂无'),
        '- 1年内：' + acts.get('1year', '暂无'),
        '',
        '---',
        '',
        '由 AI时代职业规划师 生成'
    ]
    return '\n'.join(md)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--data', default='{}')
    p.add_argument('--output-dir', default=DEFAULT_EXPORT_ROOT,
                   help='报告输出目录；必须位于 ALLOWED_EXPORT_ROOTS 之内（默认 ./exports/）')
    args = p.parse_args()

    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        print(f"[ERROR] --data 不是合法 JSON: {e}", file=sys.stderr)
        sys.exit(2)

    allowed = _load_allowed_roots()
    try:
        safe_dir = _validate_output_dir(args.output_dir, allowed)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(3)

    os.makedirs(str(safe_dir), exist_ok=True)

    md = generate_report(data)
    date_str = datetime.now().strftime('%Y%m%d')
    filename = _generate_collision_resistant_name(date_str)
    target = safe_dir / filename

    # Exclusive creation: refuse to overwrite an existing file
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(str(target), flags, 0o600)
    except FileExistsError:
        # 极小概率：随机冲突；再生成一次
        filename = _generate_collision_resistant_name(date_str)
        target = safe_dir / filename
        fd = os.open(str(target), flags, 0o600)

    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(md)
    except Exception:
        # 如果写失败，清理半成品文件
        try:
            os.unlink(str(target))
        except OSError:
            pass
        raise

    print('Markdown: ' + str(target))