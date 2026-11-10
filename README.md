# 人生账本

一个把「人生进度」当成行情来记录的移动端小应用：用欧易 OKX 风格的 K 线图，把身价、成长、健康、关系等板块的变化画成可以缩放、拖拽的蜡烛图。

单文件 HTML 实现（`index.html`，约 110KB），外层用 Capacitor 8 打包成 Android APK，并带一套自己的热更新机制（不需要重新上架即可更新页面）。

## 下载安装（Android）

最新版安装包在 Releases 页面：**[Releases](https://github.com/3372644a-max/life-ledger/releases/latest)**

- 手机直接打开 `life-ledger-v5.13.apk` 的下载链接安装即可，覆盖安装不会丢失账本数据（数据存在本地 localStorage）
- v5.12 及更早版本的壳没有「代际守卫」，热更新只能靠兜底防线事后纠正，建议升级到 v5.13

## 功能

- **多板块 K 线**：身价、成长、健康、关系等板块各自维护时间序列，切换板块即切换图表与顶部大数字
- **像素级图表交互**：按住拖拽平移、双指缩放锚定、惯性滑动、右侧留白、边缘回弹
- **顶部 Hero 数字**：单一数据源推导 + 每帧收敛 + MutationObserver 防线，保证切板块后数值不串
- **明细记录**：每个板块的每次变化都有条目，可与 K 线点位对应
- **本地存储**：所有数据保存在 localStorage，不上传任何服务器
- **热更新**：启动时检查线上 `update.js`，有新版则整页替换；带「文档代际守卫」防止旧脚本残留继续写新页面
- **诊断面板**：设置页可查看当前版本、缓存状态、热更新记录

## 目录结构

```
index.html              # 应用主体（单文件 HTML/CSS/JS）
index.bak.58.html       # v5.8 原始版本，留作对照
publish.py              # 生成 dist/update.js 并发布的脚本
dist/                   # 热更新产物（线上更新源）
icon/                   # 图标源文件与生成页
app/                    # Capacitor Android 工程
  www/index.html        # cap sync 后由 index.html 复制而来
  android/              # Android 原生壳
*.apk                   # 各版本构建产物
```

## 本地运行

直接用浏览器打开 `index.html` 即可，无需依赖、无需构建。

## 打包 Android

```bash
cd app
npm install
npx cap sync android
cd android
./gradlew assembleDebug
```

产物在 `app/android/app/build/outputs/apk/debug/app-debug.apk`。版本号在 `app/android/app/build.gradle` 的 `versionCode` / `versionName` 中维护，同时需要同步修改 `index.html` 里的 `APP_VERSION`。

## 热更新

```bash
python publish.py   # 生成 dist/update.js
```

将 `dist/` 发布到任意静态托管即可作为更新源。客户端启动时会比对版本号，发现新版则整页替换：

- 替换前先把 `window.__LEDGER_GEN__` 代数 +1，使旧壳所有定时器/回调立即失效
- 定时器包装是幂等的（`__ledgerGuarded` 标记），新文档不会再包一层把自己杀掉
- `requestAnimationFrame` 不参与守卫，避免渲染循环被误杀

## 版本记录

| 版本 | 说明 |
| --- | --- |
| v5.13 | 定位并修复热更新后旧脚本残留定时器导致的顶部数字串板块问题；新增代际守卫 + MutationObserver 防线 + 诊断面板 |
| v5.12 | 加版本水印与诊断面板，用于排查串值问题 |
| v5.11 | Hero 单一数据源重构（`heroWant` / `paintHeroBits` / `heroConverge`）|
| v5.10 | 动画序列号守卫、横盘锚点时序修正 |
| v5.9 | K 线全面欧易化：像素级平移、惯性、缩放锚定、右侧留白、边缘滚动 |
| v5.8 及更早 | 基础账本、板块切换、图表雏形 |

## 说明

账本数据只存在用户自己的设备上，仓库中的 APK 仅为历史构建产物，不包含任何用户数据。
