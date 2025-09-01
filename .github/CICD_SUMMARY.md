# GitHub Actions CI/CD 配置总结

## 📁 文件结构

```
.github/
├── workflows/
│   ├── build.yml        # 主要的构建和发布工作流（全平台）
│   ├── mobile.yml       # 专门的移动平台构建工作流
│   ├── release.yml      # 自动发布工作流
│   ├── quality.yml      # 代码质量检查工作流
│   └── README.md        # 工作流使用说明
└── copilot-instructions.md

docs/
└── MOBILE_BUILD_GUIDE.md # 移动平台构建详细指南

scripts/
├── release.sh           # 版本发布脚本
└── test-build.sh        # 本地构建测试脚本（包含移动平台）
```

## 🔄 工作流触发规则

### 1. build.yml（主构建流程）
- **推送到 main/master 分支** → 运行测试 + 构建所有平台 + 发布开发版本
- **Pull Request** → 运行测试 + 构建验证（所有平台）
- **Release 发布** → 运行测试 + 构建所有平台 + 上传到 Release

### 2. mobile.yml（移动平台专项构建）
- **推送到 main/master 分支**（移动相关文件变更时）→ 专门的移动平台构建
- **Pull Request** → 移动平台构建验证
- **手动触发** → 可手动运行移动平台构建

### 3. release.yml（自动发布）
- **推送 v* 标签**（如 v1.0.0）→ 创建 Release + 生成更改日志（包含移动平台说明）

### 4. quality.yml（代码质量）
- **推送到 main/master 分支** → 代码检查 + 安全扫描
- **Pull Request** → 代码检查 + 安全扫描

## 🏗️ 构建产物

每个平台生成的文件：

### 桌面平台
- **Linux**: `*.deb` (Debian/Ubuntu 安装包)
- **Windows**: `*.msi` (Windows 安装程序)
- **macOS**: `*.dmg` (macOS 磁盘映像)

### 移动平台
- **iOS**: Xcode 项目文件和构建日志（需要手动签名）
- **Android**: `*.apk` (未签名的调试版本) 和项目源码

## 🚀 发布策略

### 开发版本
- **触发**: 推送到主分支
- **标签**: `dev-{commit-sha}`
- **状态**: 预发布（Prerelease）
- **包含**: 所有平台构建产物（桌面 + 移动）
- **目的**: 持续部署，快速验证功能

### 正式版本
- **触发**: 推送版本标签（v1.0.0）
- **标签**: 用户定义（v1.0.0, v1.1.0 等）
- **状态**: 正式发布
- **包含**: 所有平台构建产物（桌面 + 移动）
- **目的**: 稳定版本，面向最终用户

### 移动平台特别说明
- iOS 构建生成 Xcode 项目文件，需要开发者手动签名
- Android 生成未签名的调试 APK，适用于开发和测试
- 移动平台构建失败不会阻止整体发布流程

## 🛠️ 使用方法

### 日常开发
```bash
# 开发新功能
git checkout -b feature/new-feature
# 开发、测试...
git add .
git commit -m "Add new feature"
git push origin feature/new-feature

# 创建 Pull Request，触发质量检查
# 合并到 main 后，自动构建开发版本
```

### 发布新版本
```bash
# 方法1：使用脚本（推荐）
./scripts/release.sh 1.0.0

# 方法2：手动操作
# 1. 更新版本号（pyproject.toml）
# 2. 提交并推送
# 3. 创建标签
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

## 📊 监控和调试

### 查看构建状态
- GitHub Actions 页面: `/actions`
- 实时日志和错误信息
- 构建产物下载

### 常见问题
1. **构建失败**: 检查依赖配置和测试
2. **发布失败**: 确认标签格式和权限
3. **质量检查失败**: 本地运行 `flake8`、`black` 等工具

### 本地验证
```bash
# 代码质量检查
pip install flake8 black isort mypy bandit safety
flake8 src/
black --check src/
isort --check-only src/
mypy src/ --ignore-missing-imports

# 构建测试
python -m briefcase build
python -m briefcase package
```

## 🔧 自定义配置

### 修改构建目标
编辑 `.github/workflows/build.yml`:
- 添加/删除平台支持
- 修改 Python 版本
- 调整构建参数

### 修改发布策略
编辑 `.github/workflows/release.yml`:
- 自定义 Release 说明模板
- 修改标签匹配规则
- 添加额外的发布步骤

### 添加新的检查
编辑 `.github/workflows/quality.yml`:
- 添加新的代码检查工具
- 配置安全扫描规则
- 集成代码覆盖率报告

## 🎯 最佳实践

1. **提交信息**: 使用清晰的提交信息，便于生成更改日志
2. **版本管理**: 遵循语义化版本规范（1.0.0, 1.1.0, 2.0.0）
3. **测试覆盖**: 确保新功能有对应的测试
4. **文档更新**: 重要变更时更新 README 和文档
5. **发布前验证**: 使用发布脚本确保流程正确

## 📈 扩展建议

未来可以考虑添加：
- 自动化测试报告
- 性能基准测试
- 应用签名和公证
- 应用商店自动发布
- 多语言本地化检查
- 用户反馈收集
