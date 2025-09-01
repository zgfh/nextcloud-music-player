#!/bin/bash

# 发布脚本 - 用于创建新的版本标签和发布

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查是否在正确的分支
check_branch() {
    current_branch=$(git branch --show-current)
    if [ "$current_branch" != "main" ] && [ "$current_branch" != "master" ]; then
        print_error "请切换到 main 或 master 分支后再发布"
        exit 1
    fi
    print_success "当前在 $current_branch 分支"
}

# 检查工作区是否干净
check_clean_workspace() {
    if [ -n "$(git status --porcelain)" ]; then
        print_error "工作区有未提交的更改，请先提交或暂存"
        git status --short
        exit 1
    fi
    print_success "工作区干净"
}

# 获取当前版本
get_current_version() {
    # 从 pyproject.toml 中读取版本
    current_version=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
    echo "$current_version"
}

# 更新版本号
update_version() {
    local new_version=$1
    print_info "更新版本号到 $new_version"
    
    # 更新 pyproject.toml 中的版本
    sed -i.bak "s/^version = .*/version = \"$new_version\"/" pyproject.toml
    sed -i.bak "s/^version = .*/version = \"$new_version\"/" pyproject.toml
    
    # 删除备份文件
    rm -f pyproject.toml.bak
    
    print_success "版本号已更新"
}

# 创建提交和标签
create_release() {
    local version=$1
    local tag="v$version"
    
    print_info "创建发布提交和标签"
    
    # 添加更改的文件
    git add pyproject.toml
    
    # 创建提交
    git commit -m "Release version $version"
    
    # 创建标签
    git tag -a "$tag" -m "Release version $version"
    
    print_success "已创建标签 $tag"
}

# 推送到远程
push_release() {
    local tag=$1
    
    print_info "推送到远程仓库"
    
    # 推送代码和标签
    git push origin HEAD
    git push origin "$tag"
    
    print_success "已推送到远程仓库"
}

# 主函数
main() {
    echo "🚀 NextCloud Music Player 发布脚本"
    echo "=================================="
    
    # 检查参数
    if [ $# -eq 0 ]; then
        print_error "用法: $0 <版本号>"
        print_info "示例: $0 1.0.0"
        exit 1
    fi
    
    local new_version=$1
    
    # 验证版本号格式
    if ! [[ $new_version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        print_error "版本号格式无效，请使用 x.y.z 格式（如 1.0.0）"
        exit 1
    fi
    
    # 执行检查
    print_info "执行发布前检查..."
    check_branch
    check_clean_workspace
    
    # 获取当前版本
    current_version=$(get_current_version)
    print_info "当前版本: $current_version"
    print_info "新版本: $new_version"
    
    # 确认发布
    echo
    print_warning "即将发布版本 $new_version，这将："
    echo "  1. 更新 pyproject.toml 中的版本号"
    echo "  2. 创建发布提交"
    echo "  3. 创建版本标签 v$new_version"
    echo "  4. 推送到远程仓库"
    echo "  5. 触发 GitHub Actions 自动构建和发布"
    echo
    read -p "确认继续？(y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "已取消发布"
        exit 0
    fi
    
    # 执行发布流程
    print_info "开始发布流程..."
    
    update_version "$new_version"
    create_release "$new_version"
    push_release "v$new_version"
    
    echo
    print_success "🎉 发布完成！"
    print_info "GitHub Actions 将自动构建并创建 release"
    print_info "查看构建状态: https://github.com/zgfh/nextcloud-music-player/actions"
    print_info "查看发布页面: https://github.com/zgfh/nextcloud-music-player/releases"
}

# 执行主函数
main "$@"
