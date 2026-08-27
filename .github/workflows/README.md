# GitHub Actions 工作流说明

本项目配置了 4 条 CI/CD 工作流。构建统一使用 **flet build** 工具链（Flutter 3.44.8 + flet 0.86.5，与本地 `scripts/deploy_iso.sh` 一致）。

## 工作流概览

### 1. Code Quality (`quality.yml`)

**触发:** push 到 main/master、PR 到 main/master

**功能（纯 Python 检查，约 30s）:**
- flake8 语法/未定义名称门禁（E9,F63,F7,F82，阻塞）
- black / isort 格式检查（阻塞；isort 使用 `profile=black`，见 `pyproject.toml`）
- mypy 类型检查（非阻塞）
- bandit / safety 安全扫描（非阻塞，报告上传 artifact）

**本地对应命令:**
```bash
uv run black --check src/ && uv run isort --check-only src/
uv run flake8 src/ --select=E9,F63,F7,F82
```

### 2. E2E Tests (`e2e.yml`)

**触发:** push 到 main、PR 到 main、手动

**功能:**
- `unit` job：全量 pytest（无头交互测试，51 个用例）
- `flet-e2e` job：macOS runner 启动 iOS 模拟器跑 `flet test ios --tests-dir tests/e2e`（真实 Flutter 渲染管线）
  - 首次 provision 较慢（下载 embedded Python + 编译测试宿主），整个 job 约 10 分钟
  - **已知问题**：flet 0.86.5 device 模式下 Dart 侧 testWidgets 收尾以 exit 1 结束（无异常输出），teardown 误报 ERROR；Python 断言通过即算通过，job 已标 `continue-on-error`，等上游修复后移除

### 3. Build and Release (`build.yml`)

**触发:** push 到 main、PR 到 main、发布 Release、手动

**功能:**
- `test` job：全量 pytest 作为构建门禁
- 5 个平台构建 job（`flet build`，产物上传 artifact）：

| Job | 命令 | 产物 |
|---|---|---|
| build-android | `flet build apk` | `.apk` |
| build-linux | `flet build linux` | bundle 目录打 tar.gz（apt 装 gstreamer 供 flet-audio） |
| build-windows | `flet build windows` | Release 目录打 zip（`PYTHONUTF8=1` 防 emoji 编码崩溃） |
| build-macos | `flet build macos` | `.app` 打 zip（ad-hoc 签名，分发需重签） |
| build-ios | `flet build ios-simulator` | 模拟器 `.app` 打 zip（免签名编译验证） |

  - 所有 upload-artifact 均 `if-no-files-found: error`，产物缺失直接失败
- `publish-dev`：**仅 main push** 触发，创建 `dev-{sha}` 预发布；PR 不刷 release
- `publish-release`：GitHub Release 发布时把 5 平台产物挂到 Release

**iOS 真机签名包**：CI 无证书不出正式 IPA，由本地 `scripts/deploy_iso.sh`（自动签名 + 装机 + 续签）完成。

### 4. Auto Release (`release.yml`)

**触发:** 推送 `v*` tag（如 `v1.0.0`）

**功能:** 自动生成 changelog 并创建 GitHub Release。

## 发布流程

### 开发版本
push 到 main 即自动发布 `dev-{commit-sha}` 预发布（含 5 平台产物）。

### 正式版本

方式一（推荐）——发布脚本：
```bash
./scripts/release.sh 1.0.0   # 改版本号 → 提交 → 打 tag → 推送
```

方式二——手动：
```bash
# 编辑 pyproject.toml 版本号后
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin main --tags
```

tag 触发 `release.yml` 创建 Release；在 Release 页面发布时触发 `build.yml` 的 `publish-release` 挂载产物。

## 监控构建状态

- **Actions**: https://github.com/zgfh/nextcloud-music-player/actions
- **Releases**: https://github.com/zgfh/nextcloud-music-player/releases
