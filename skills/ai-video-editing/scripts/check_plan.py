"""Read a local editorial plan. Never fetch media, grant approval or run an editor."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit


def require(ok, message):
    if not ok:
        raise ValueError(message)


def word(row, key):
    val = row.get(key)
    require(isinstance(val, str) and val.strip(), f"{row.get('id', '计划')} 缺少 {key}")
    return val.strip()


def ids(values, label):
    require(isinstance(values, list), f"{label} 应为 ID 列表")
    require(all(isinstance(x, str) and x.strip() for x in values), f"{label} 含空 ID")
    require(len(set(values)) == len(values), f"{label} 存在重复 ID")
    return values


def index(plan, key):
    rows = plan.get(key)
    require(isinstance(rows, list), f"{key} 应为记录列表")
    result = {}
    for row in rows:
        require(isinstance(row, dict), f"{key} 含无效记录")
        name = word(row, "id")
        require(name not in result, f"{key} 的 ID 重复：{name}")
        result[name] = row
    return result


def details(row):
    require(row.get("state") != "research", f"{row['id']} 仍在查证作品或使用许可")
    fields = ("id", "url", "variant", "license", "license_url", "cost")
    # A private recording can carry permission in the project correspondence.
    # Keep the original fingerprint for records that already have a license URL.
    private_basis = row.get("origin") == "user" and not row.get("license_url")
    values = [word(row, "permission_evidence" if private_basis and key == "license_url" else key)
              for key in fields]
    url_fields = ("url",) if private_basis else ("url", "license_url")
    for key in url_fields:
        url = urlsplit(row[key])
        require(url.scheme in ("http", "https") and url.hostname, f"{row['id']} 的 {key} 需要作品或许可页面地址")
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode("utf-8")).hexdigest()[:20]


def recorded_decision(record, revision, description):
    require(isinstance(record, dict) and record.get("revision") == revision, f"待用户确认{description} {revision}")
    word(record, "evidence")


def accepted(row, approvals):
    key = details(row)
    entries = approvals.get("downloads", [])
    require(isinstance(entries, list) and all(isinstance(x, dict) for x in entries), "downloads 应为授权记录列表")
    require(any(x.get("id") == row["id"] and x.get("key") == key
                and isinstance(x.get("evidence"), str) and x["evidence"].strip() for x in entries),
            f"{row['id']} 当前作品、版本、费用及许可组合尚无用户授权")


def validate(plan, stage, selected, base):
    require(isinstance(plan, dict), "计划应为对象")
    revision = word(plan, "revision")
    require(plan.get("timebase") in ("estimated", "audio", "picture"), "timebase 应为 estimated、audio 或 picture")
    lines, media, shots = (index(plan, k) for k in ("lines", "assets", "shots"))
    require(shots, "时间轴为空")
    for row in lines.values():
        word(row, "text")
    for row in media.values():
        word(row, "purpose")
        word(row, "kind")
        require(row.get("origin") in ("web", "generated", "user"), f"{row['id']} 的来源分类无效")
        require(row.get("state") in ("research", "candidate", "requested", "ready"), f"{row['id']} 的备料状态无效")
        require(type(row.get("needs_download")) is bool, f"{row['id']} 须声明是否要从网站下载")
    used, covered = set(), set()
    end = 0
    for shot in shots.values():
        start_ms, end_ms = shot.get("from_ms"), shot.get("to_ms")
        require(type(start_ms) is int and type(end_ms) is int and start_ms == end and end_ms > start_ms,
                f"{shot['id']} 主时间轴有缺口、重叠或无效时长")
        end = end_ms
        for key in ("picture", "layout", "motion", "transition", "subtitle", "bgm", "sfx"):
            word(shot, key)
        line_ids = ids(shot.get("lines"), "镜头原句")
        media_ids = ids(shot.get("assets"), "镜头素材")
        require(media_ids, f"{shot['id']} 缺少镜头素材；文字、遮罩和图形也请作为 generated 素材登记")
        require(set(line_ids) <= lines.keys(), f"{shot['id']} 引用了不存在的原句")
        require(set(media_ids) <= media.keys(), f"{shot['id']} 引用了不存在的素材")
        if not line_ids:
            word(shot, "silent_reason")
        covered.update(line_ids)
        used.update(media_ids)
    require(covered == lines.keys(), "时间轴漏句：" + ", ".join(sorted(lines.keys()-covered)))
    require(type(plan.get("end_ms")) is int and end == plan["end_ms"], "片尾时码与计划总时长不符")
    approvals = plan.get("approvals", {})
    require(isinstance(approvals, dict), "approvals 应为对象")
    if stage == "proposal":
        require(not selected, "仅在核对下载清单时使用 --asset")
        print(f"提案 {revision}：{len(lines)} 句、{len(shots)} 镜，{end/1000:g} 秒；尚不执行下载或剪辑。")
        for row in media.values():
            if row["needs_download"]:
                if row["state"] == "research":
                    print(f"  {row['id']} 待查证，暂不列入下载确认单。")
                else:
                    print(f"  {row['id']} {details(row)}  {row['url']}  {row['variant']}  {row['cost']}")
        return
    if stage == "download":
        require(selected, "请用 --asset 指定本次要取的素材 ID；没有默认全部下载")
        for name in ids(selected, "本批下载"):
            require(name in used and media[name]["needs_download"], f"{name} 未列入当前镜头需要下载的项目，本批不取")
            accepted(media[name], approvals)
        print("本批授权记录匹配：" + ", ".join(selected) + "。未执行下载。")
        return
    require(not selected, "开剪核对覆盖整条时间轴，不接受 --asset")
    recorded_decision(approvals.get("plan"), revision, "包装方案")
    recorded_decision(approvals.get("edit"), revision, "备齐后开剪")
    for name in sorted(used):
        row = media[name]
        if row["needs_download"]:
            accepted(row, approvals)
        require(row["state"] == "ready", f"{name} 尚未备齐")
        if row["origin"] == "generated" and row["kind"] == "graphic" and row.get("inline_design"):
            word(row, "inline_design")
        else:
            require((base / word(row, "path")).is_file(), f"{name} 本机文件不存在")
        if row["origin"] == "web":
            details(row)
    print(f"{revision} 结构、已用素材文件及授权记录已通过；实际用途、音画和用户原话需由编辑核对。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--stage", choices=("proposal", "download", "edit"), default="proposal")
    parser.add_argument("--asset", action="append", default=[])
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
        validate(plan, args.stage, args.asset, args.plan.parent)
    except (OSError, ValueError) as error:
        print(f"未通过：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
