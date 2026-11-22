"""Make a local HTML preview from a pinned HyperFrames composition and real stills."""

import argparse
from html import escape
import json
from pathlib import Path
import re
import sys


REGISTRY = Path(__file__).resolve().parents[1] / "upstream/heygen-hyperframes/registry"
ITEMS = {"name": "lt-clean-bar", "compare": "before-after-wipe", "screen": "browser-device-stage"}
CDN = '<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>'


def uri(path, extensions):
    resolved = path.resolve(strict=True)
    if resolved.suffix.lower() not in extensions or not resolved.is_file():
        raise ValueError(f"Expected a local {', '.join(extensions)} file: {path}")
    return resolved.as_uri()


def runtime_path(explicit):
    if explicit:
        return uri(explicit, (".js",))
    raise ValueError("Supply the path of an existing local GSAP 3 runtime with --gsap")


def prepare(args):
    item = ITEMS[args.kind]
    source = (REGISTRY / item / (item + ".html")).read_text(encoding="utf-8")
    original_head, body = source.split("<body>", 1)
    body = body.split("</body>", 1)[0].strip()
    styles = "\n".join(re.findall(r"<style>.*?</style>", original_head, re.S))
    body = body.removeprefix("<template>").removesuffix("</template>").strip()
    if CDN not in (original_head + body):
        raise ValueError("Upstream script declaration changed")
    body = body.replace(CDN, "")
    variables, slot_images, names = {}, {}, {}
    images = (".png", ".jpg", ".jpeg", ".webp")
    if args.kind == "name":
        names = {"lt-name": args.name, "lt-role": args.role}
    elif args.kind == "compare":
        variables = {"label_a": args.before_label, "label_b": args.after_label}
        slot_images = {"before": uri(args.before, images), "after": uri(args.after, images)}
    else:
        variables = {"title": args.title, "chrome": "window", "swap_at": 2 if args.next else 0}
        slot_images = {"browser-device-stage-screen": uri(args.image, images)}
        if args.next:
            slot_images["browser-device-stage-screen-b"] = uri(args.next, images)
    config = json.dumps([variables, names, slot_images], ensure_ascii=False).replace("<", "\\u003c")
    setup = """<script>
const [variables, names, slots] = CONFIG;
window.__hyperframes = {getVariables: () => variables};
for (const [id, value] of Object.entries(names)) document.getElementById(id).textContent = value;
for (const [key, url] of Object.entries(slots)) {
  const image = new Image(); image.src = url; image.style.objectFit = 'contain';
  const own = document.querySelector('[data-slot="' + key + '"]');
  if (own) { own.replaceChildren(image); continue; }
  const template = document.createElement('template'); template.dataset.slot = key;
  template.content.append(image); document.body.append(template);
}
</script>""".replace("CONFIG", config)
    # Insert slot data after the upstream markup, before its first inline timeline script.
    if "<script>" not in body:
        raise ValueError("Cannot find upstream timeline script")
    body = body.replace("<script>", setup + "\n<script>", 1)
    styles += """<style>html,body{width:100%;height:100%;margin:0;overflow:hidden;background:#20262e}
main{width:1920px;height:1080px;position:absolute;left:50%;top:50%;transform-origin:0 0}
main>#root{position:absolute;inset:0}</style>"""
    boot = """<script>
const stage = document.querySelector('main');
function resize(){stage.style.transform = 'scale('+Math.min(innerWidth/1920,innerHeight/1080)+') translate(-50%,-50%)';}
resize(); addEventListener('resize',resize);
const timeline = window.__timelines[ITEM];
const at = new URLSearchParams(location.search).get('t');
if (at !== null && Number.isFinite(Number(at))) timeline.pause(Math.max(0,Number(at)));
else timeline.repeat(-1).repeatDelay(.6).play(0);
</script>""".replace("ITEM", json.dumps(item))
    runtime = escape(runtime_path(args.gsap), quote=True)
    return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{item}</title>'
            f'{styles}<script src="{runtime}"></script></head><body><main>{body}</main>{boot}</body></html>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="A new .html file")
    parser.add_argument("--gsap", type=Path, required=True, help="Path to a local GSAP 3 runtime (gsap.min.js)")
    kinds = parser.add_subparsers(dest="kind", required=True)
    name = kinds.add_parser("name")
    name.add_argument("--name", required=True)
    name.add_argument("--role", required=True)
    compare = kinds.add_parser("compare")
    compare.add_argument("--before", type=Path, required=True)
    compare.add_argument("--after", type=Path, required=True)
    compare.add_argument("--before-label", default="调整前")
    compare.add_argument("--after-label", default="调整后")
    screen = kinds.add_parser("screen")
    screen.add_argument("--image", type=Path, required=True)
    screen.add_argument("--next", type=Path)
    screen.add_argument("--title", required=True)
    args = parser.parse_args()
    try:
        if args.output.suffix.lower() != ".html":
            raise ValueError("Expected an .html output")
        document = prepare(args)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(document)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Preview unavailable: {error}\n")


if __name__ == "__main__":
    main()
