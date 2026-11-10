"""人生账本 · 更新包生成脚本

用法：python publish.py
作用：把 index.html 打包成 dist/update.js（供 App 内「检查更新」下载）。
生成后需要把 dist 目录重新发布一次，手机上才会收到更新。

流程（以后每次发新版）：
  1. 改 index.html 里的 APP_VERSION 和 app/android/app/build.gradle 的 versionName
  2. python publish.py
  3. 重新发布 dist 目录
  4. 手机上：设置 → 检查更新 → 重启应用
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "dist")


def main():
    html = io.open(SRC, encoding="utf-8").read()
    m = re.search(r'const APP_VERSION = "([^"]+)"', html)
    if not m:
        raise SystemExit("找不到 APP_VERSION，请检查 index.html")
    ver = m.group(1)

    if not os.path.isdir(OUT):
        os.makedirs(OUT)

    pkg = json.dumps({"version": ver, "html": html}, ensure_ascii=False)
    js = "/* 人生账本 更新包 v%s —— 请勿手动修改 */\nwindow.__LEDGER_UPD__ = %s;\n" % (ver, pkg)
    # </script> 与 <!-- 会提前结束脚本标签，需要转义
    js = js.replace("</", "<\\/").replace("<!--", "<\\!--")

    io.open(os.path.join(OUT, "update.js"), "w", encoding="utf-8").write(js)
    io.open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
    io.open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8").write(
        json.dumps({"version": ver, "file": "update.js"}, ensure_ascii=False)
    )

    print("版本      : v%s" % ver)
    print("update.js : %.1f KB" % (len(js.encode("utf-8")) / 1024.0))
    print("下一步    : 重新发布 dist 目录，然后手机上 设置 → 检查更新")


if __name__ == "__main__":
    main()
