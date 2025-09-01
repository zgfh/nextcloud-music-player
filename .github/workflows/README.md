# GitHub Actions 工作流说明

本项目配置了完整的 CI/CD 工作流，支持自动构建、测试和发布，包括桌面和移动平台。

## 🔧 工作流概览

### 1. Build and Release (`build.yml`)
**触发条件:**
- 推送到 `main` 或 `master` 分支
- Pull Request 到 `main` 或 `master` 分支
- 发布 Release

**功能:**
- 运行单元测试
- 构建多平台应用包 (Linux、Windows、macOS、iOS、Android)
- 自动发布开发版本（推送到主分支时）
- 上传制品到 Release（创建正式发布时）

### 2. Mobile Build (`mobile.yml`)
**触发条件:**
- 推送到 `main` 或 `master` 分支（仅当移动相关文件变更时）
- Pull Request
- 手动触发

**功能:**
- 专门的移动平台构建流程
- iOS 项目生成和构建
- Android APK 生成
- 详细的构建日志和错误报告

### 3. Auto Release (`release.yml`)
**触发条件:**
- 推送以 `v` 开头的标签（如 `v1.0.0`）

**功能:**
- 自动创建 GitHub Release
- 生成更改日志
- 添加详细的发布说明（包含移动平台安装指导）

### 4. Code Quality (`quality.yml`)
**触发条件:**
- 推送到 `main` 或 `master` 分支
- Pull Request 到 `main` 或 `master` 分支

**功能:**
- 代码格式检查 (black, isort)
- 代码质量检查 (flake8)
- 类型检查 (mypy)
- 安全扫描 (bandit, safety)

## 🚀 发布流程

### 开发版本发布
每次推送到 `main` 或 `master` 分支时，会自动创建开发版本：

```bash
git add .
git commit -m "Add new feature"
git push origin main
```

这将触发：
1. 运行测试
2. 构建所有平台的应用包
3. 创建标签为 `dev-{commit-sha}` 的预发布版本

### 正式版本发布

#### 方法1：使用发布脚本（推荐）
```bash
# 发布新版本（如 1.0.0）
./scripts/release.sh 1.0.0
```

脚本会自动：
1. 检查当前分支和工作区状态
2. 更新 `pyproject.toml` 中的版本号
3. 创建发布提交
4. 创建版本标签
5. 推送到远程仓库

#### 方法2：手动操作
```bash
# 1. 更新版本号（编辑 pyproject.toml）
# 2. 提交更改
git add pyproject.toml
git commit -m "Release version 1.0.0"

# 3. 创建标签
git tag -a v1.0.0 -m "Release version 1.0.0"

# 4. 推送
git push origin main
git push origin v1.0.0
```

## 📦 构建产物

工作流会为每个平台生成以下文件：

### 桌面平台
- **Linux**: `.deb` 安装包
- **Windows**: `.msi` 安装包  
- **macOS**: `.dmg` 安装包

### 移动平台
- **iOS**: Xcode 项目文件和构建日志（需要手动签名和安装）
- **Android**: `.apk` 文件（未签名的调试版本）和项目文件

### 移动平台注意事项
- iOS 构建需要 macOS 环境和 Xcode
- Android 构建生成的是调试版 APK，未经签名
- 移动平台构建可能因为环境配置问题而失败，但会继续其他平台的构建
- 构建失败时会上传构建日志以便调试

## 🔍 监控构建状态

- **Actions 页面**: https://github.com/zgfh/nextcloud-music-player/actions
- **Releases 页面**: https://github.com/zgfh/nextcloud-music-player/releases

## ⚙️ 环境变量和密钥

当前工作流使用的是 GitHub 自动提供的 `GITHUB_TOKEN`，无需额外配置。

如需添加其他功能（如发布到应用商店），可能需要配置额外的密钥：

1. 进入仓库的 Settings > Secrets and variables > Actions
2. 添加所需的密钥（如 `APPLE_DEVELOPER_ID`、`WINDOWS_CERTIFICATE` 等）

## 🐛 故障排除

### 构建失败
1. 检查 Actions 页面的错误日志
2. 确保所有依赖都在 `pyproject.toml` 中正确配置
3. 验证代码通过本地测试

### 发布失败
1. 确保标签格式正确（`v1.0.0` 格式）
2. 检查是否有权限问题
3. 验证工作流文件语法

### 代码质量检查失败
```bash
# 本地运行检查
pip install flake8 black isort mypy
flake8 src/
black src/
isort src/
mypy src/ --ignore-missing-imports
```

## 📝 自定义工作流

如需修改工作流行为，可以编辑 `.github/workflows/` 目录下的文件：

- `build.yml`: 修改构建和发布逻辑
- `release.yml`: 修改自动发布行为
- `quality.yml`: 修改代码质量检查规则

记得在修改后测试工作流是否正常运行。
