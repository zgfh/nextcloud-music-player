#!/bin/bash
# ============================================================================
# debug_server.sh - 手机 Flet 客户端远程调试部署脚本
#
# 一键部署/重启整套调试链路：
#   Mac 应用服务器(59999, UUID路径) ◄─ssh隧道─ gouyun虚拟网卡(10.99.0.1:59999)
#                                       ▲
#                          手机 Flet 应用（需 VPN 出口在 gouyun）
#
# 用法:
#   ./debug_server.sh start          # 全量部署（缺啥补啥），打印手机访问地址
#   ./debug_server.sh stop           # 停应用 + 停隧道
#   ./debug_server.sh restart        # stop + start
#   ./debug_server.sh restart-app    # 只重启应用（改完代码后用，隧道不动）
#   ./debug_server.sh status         # 查看各组件状态与访问地址
#   ./debug_server.sh log [app|tunnel]  # 跟踪日志（默认 app）
#   ./debug_server.sh start --new-uuid  # 轮换访问路径 UUID（手机端需换地址）
#   ./debug_server.sh start --port 59999 # 指定本机服务及远端隧道端口
#   ./debug_server.sh start --web-port 60000 # 指定 Web 模式端口
#   ./debug_server.sh start --secure       # 可选：启用 UUID 路径和 Web 令牌
#
# 依赖: ssh gouyun 可免密登录（root）；.venv 已装 flet/uvicorn/fastapi
# ============================================================================

set -euo pipefail

# ---------- 配置 ----------
SSH_HOST="${DEBUG_SSH_HOST:-gouyun}"
REMOTE_BIND_IP="${DEBUG_BIND_IP:-10.253.99.1}"    # gouyun 上虚拟网卡 ncmp0 的 IP
REMOTE_NIC="${DEBUG_REMOTE_NIC:-ncmp0}"
REMOTE_PORT="${DEBUG_REMOTE_PORT:-59999}"
LOCAL_PORT="${DEBUG_LOCAL_PORT:-59999}"
WEB_PORT="${DEBUG_WEB_PORT:-60000}"
LOCAL_BIND_IP="${DEBUG_LOCAL_BIND_IP:-0.0.0.0}"
SECURE_ACCESS="${DEBUG_SECURE_ACCESS:-0}"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEBUG_DIR="$PROJECT_DIR/.debug"
LOG_DIR="$DEBUG_DIR/logs"
UUID_FILE="$DEBUG_DIR/uuid"
APP_PID_FILE="$DEBUG_DIR/app.pid"
WEB_PID_FILE="$DEBUG_DIR/web.pid"
WEB_TOKEN_FILE="$DEBUG_DIR/web-token"
TUNNEL_PID_FILE="$DEBUG_DIR/tunnel.pid"
STOP_FLAG="$DEBUG_DIR/tunnel.stop"

mkdir -p "$LOG_DIR"

# ---------- 工具函数 ----------
cyan()  { printf '\033[36m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }

get_uuid() {
    if [[ ! -s "$UUID_FILE" ]]; then
        .venv/bin/python -c "import uuid; print(uuid.uuid4().hex[:12])" > "$UUID_FILE" 2>/dev/null \
            || uuidgen | tr -d '-' | cut -c1-12 > "$UUID_FILE"
    fi
    cat "$UUID_FILE"
}

get_web_token() {
    if [[ ! -s "$WEB_TOKEN_FILE" ]]; then
        .venv/bin/python -c "import secrets; print(secrets.token_hex(16))" > "$WEB_TOKEN_FILE"
        chmod 600 "$WEB_TOKEN_FILE"
    fi
    cat "$WEB_TOKEN_FILE"
}

access_path() {
    [[ "$SECURE_ACCESS" == "1" ]] && echo "/$(get_uuid)" || echo "/"
}
phone_url()  { echo "http://${REMOTE_BIND_IP}:${REMOTE_PORT}$(access_path)"; }
local_ip() {
    local iface
    iface=$(route -n get default 2>/dev/null | awk '/interface:/{print $2}')
    ipconfig getifaddr "$iface" 2>/dev/null || echo "127.0.0.1"
}
local_url()  { echo "http://$(local_ip):${LOCAL_PORT}$(access_path)"; }
web_phone_url() {
    if [[ "$SECURE_ACCESS" == "1" ]]; then
        echo "http://${REMOTE_BIND_IP}:${WEB_PORT}/?k=$(get_web_token)"
    else
        echo "http://${REMOTE_BIND_IP}:${WEB_PORT}/"
    fi
}
web_local_url() {
    if [[ "$SECURE_ACCESS" == "1" ]]; then
        echo "http://$(local_ip):${WEB_PORT}/?k=$(get_web_token)"
    else
        echo "http://$(local_ip):${WEB_PORT}/"
    fi
}
flet_link()  { echo "flet://flet-host/$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote('$(phone_url)', safe=''))")"; }

is_running() {  # is_running <pidfile>
    [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null
}

wait_port() {  # wait_port <端口> <超时秒>
    local port=$1 timeout=$2 waited=0
    while ! lsof -i ":$port" -sTCP:LISTEN >/dev/null 2>&1; do
        sleep 1
        waited=$((waited + 1))
        if (( waited >= timeout )); then return 1; fi
    done
    return 0
}

# ---------- 组件：应用服务器 ----------
start_app() {
    if is_running "$APP_PID_FILE"; then
        cyan "[app] 已在运行 (pid $(cat "$APP_PID_FILE"))，跳过（restart-app 可强制重启）"
        return
    fi
    # 端口被不明旧实例占用时先清掉，否则新进程绑定失败会直接崩
    local stale
    stale=$(lsof -ti ":$LOCAL_PORT" -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "$stale" ]]; then
        red "[app] 端口 $LOCAL_PORT 被旧实例占用 (pid $stale)，强制清理"
        kill $stale 2>/dev/null || true
        sleep 1
        stale=$(lsof -ti ":$LOCAL_PORT" -sTCP:LISTEN 2>/dev/null || true)
        [[ -n "$stale" ]] && kill -9 $stale 2>/dev/null || true
    fi
    local path
    path=$(access_path)
    cyan "[app] 启动 Flet 服务器 (${LOCAL_BIND_IP}:${LOCAL_PORT}, 路径 ${path}) ..."
    (
        cd "$PROJECT_DIR"
        FLET_FORCE_WEB_SERVER=true \
        FLET_SERVER_PORT="$LOCAL_PORT" \
        FLET_SERVER_IP="$LOCAL_BIND_IP" \
        FLET_WEB_APP_PATH="${path#/}" \
        nohup .venv/bin/python run.py >> "$LOG_DIR/app.log" 2>&1 < /dev/null &
        echo $! > "$APP_PID_FILE"
    )
    if wait_port "$LOCAL_PORT" 90; then
        green "[app] 就绪 (pid $(cat "$APP_PID_FILE"))"
    else
        red "[app] 90 秒内未监听 ${LOCAL_PORT}，查看日志: $LOG_DIR/app.log"
        exit 1
    fi
}

stop_app() {
    if is_running "$APP_PID_FILE"; then
        local pid
        pid=$(cat "$APP_PID_FILE")
        kill "$pid" 2>/dev/null || true
        sleep 1
        kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
        green "[app] 已停止"
    fi
    # 兜底：按端口清残留（含不认识的旧实例），SIGTERM 无效则升级 SIGKILL
    local pids
    pids=$(lsof -ti ":$LOCAL_PORT" -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        kill $pids 2>/dev/null || true
        sleep 1
        pids=$(lsof -ti ":$LOCAL_PORT" -sTCP:LISTEN 2>/dev/null || true)
        [[ -n "$pids" ]] && kill -9 $pids 2>/dev/null || true
    fi
    rm -f "$APP_PID_FILE"
}

start_web() {
    if is_running "$WEB_PID_FILE"; then
        cyan "[web] 已在运行 (pid $(cat "$WEB_PID_FILE"))，跳过"
        return
    fi
    local stale token web_gate_env
    stale=$(lsof -ti ":$WEB_PORT" -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "$stale" ]]; then
        red "[web] 端口 $WEB_PORT 被旧实例占用 (pid $stale)，强制清理"
        kill $stale 2>/dev/null || true
        sleep 1
    fi
    token=""
    web_gate_env=1
    if [[ "$SECURE_ACCESS" == "1" ]]; then
        token=$(get_web_token)
        web_gate_env=0
    fi
    cyan "[web] 启动浏览器模式 (${LOCAL_BIND_IP}:${WEB_PORT}) ..."
    (
        cd "$PROJECT_DIR"
        WEB_ACCESS_TOKEN="$token" WEB_DISABLE_TOKEN_GATE="$web_gate_env" \
            nohup .venv/bin/python run_web.py \
            --lan --no-browser --port="$WEB_PORT" >> "$LOG_DIR/web.log" 2>&1 < /dev/null &
        echo $! > "$WEB_PID_FILE"
    )
    if wait_port "$WEB_PORT" 90; then
        green "[web] 就绪 (pid $(cat "$WEB_PID_FILE"))"
    else
        red "[web] 90 秒内未监听 ${WEB_PORT}，查看日志: $LOG_DIR/web.log"
        exit 1
    fi
}

stop_web() {
    if is_running "$WEB_PID_FILE"; then
        local pid
        pid=$(cat "$WEB_PID_FILE")
        kill "$pid" 2>/dev/null || true
        sleep 1
        kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
        green "[web] 已停止"
    fi
    local pids
    pids=$(lsof -ti ":$WEB_PORT" -sTCP:LISTEN 2>/dev/null || true)
    [[ -n "$pids" ]] && kill $pids 2>/dev/null || true
    rm -f "$WEB_PID_FILE"
}

# ---------- 组件：gouyun 虚拟网卡 ----------
ensure_remote_nic() {
    cyan "[nic] 检查 ${SSH_HOST} 的 ${REMOTE_NIC} (${REMOTE_BIND_IP}) ..."
    if ssh -o ConnectTimeout=15 -o BatchMode=yes "$SSH_HOST" \
        "ip -4 addr show $REMOTE_NIC | grep -q '$REMOTE_BIND_IP/'" 2>/dev/null; then
        green "[nic] 已存在"
    else
        ssh -o ConnectTimeout=15 -o BatchMode=yes "$SSH_HOST" "
            ip link add $REMOTE_NIC type dummy 2>/dev/null || true
            ip addr flush dev $REMOTE_NIC
            ip addr add ${REMOTE_BIND_IP}/24 dev $REMOTE_NIC
            ip link set $REMOTE_NIC up
        " 2>/dev/null
        green "[nic] 已创建 ${REMOTE_NIC} = ${REMOTE_BIND_IP}/24"
    fi

    # sshd 必须允许客户端指定绑定地址（缺失时自动补 drop-in，校验后再 reload）
    local gp
    gp=$(ssh -o ConnectTimeout=15 -o BatchMode=yes "$SSH_HOST" "sshd -T 2>/dev/null | grep -i '^gatewayports '" 2>/dev/null || true)
    if [[ "$gp" != *"clientspecified"* ]]; then
        cyan "[nic] 补充 sshd GatewayPorts=clientspecified ..."
        ssh -o ConnectTimeout=15 -o BatchMode=yes "$SSH_HOST" '
            printf "GatewayPorts clientspecified\n" > /etc/ssh/sshd_config.d/10-gatewayports.conf
            sshd -t && (systemctl reload sshd 2>/dev/null || service ssh reload) || rm -f /etc/ssh/sshd_config.d/10-gatewayports.conf
        ' 2>/dev/null
        green "[nic] GatewayPorts 就绪"
    fi
}

# ---------- 组件：SSH 隧道（带断线自动重连循环） ----------
start_tunnel() {
    if is_running "$TUNNEL_PID_FILE"; then
        cyan "[tunnel] 已在运行 (pid $(cat "$TUNNEL_PID_FILE"))，跳过"
        return
    fi
    rm -f "$STOP_FLAG"
    cyan "[tunnel] 建立原生 ${REMOTE_PORT} 与 Web ${WEB_PORT} 双端口隧道 ..."
    # 关键：整个守护循环的 stdin/stdout 全部脱离调用方管道，
    # 否则调用方（如 tail/管道场景）会因循环持有写端而永远等不到 EOF
    nohup bash -c "
        while [[ ! -f '$STOP_FLAG' ]]; do
            ssh -N \
                -R '${REMOTE_BIND_IP}:${REMOTE_PORT}:127.0.0.1:${LOCAL_PORT}' \
                -R '${REMOTE_BIND_IP}:${WEB_PORT}:127.0.0.1:${WEB_PORT}' \
                -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
                -o ExitOnForwardFailure=yes -o ConnectTimeout=20 \
                '$SSH_HOST' >> '$LOG_DIR/tunnel.log' 2>&1
            [[ -f '$STOP_FLAG' ]] && break
            echo \"\$(date '+%F %T') 隧道断开，3 秒后重连\" >> '$LOG_DIR/tunnel.log'
            sleep 3
        done
    " < /dev/null >> "$LOG_DIR/tunnel.log" 2>&1 &
    echo $! > "$TUNNEL_PID_FILE"
    sleep 5
    if is_running "$TUNNEL_PID_FILE"; then
        green "[tunnel] 守护循环已启动 (pid $(cat "$TUNNEL_PID_FILE"))"
    else
        red "[tunnel] 启动失败，查看日志: $LOG_DIR/tunnel.log"
        exit 1
    fi
}

stop_tunnel() {
    touch "$STOP_FLAG"
    if is_running "$TUNNEL_PID_FILE"; then
        kill "$(cat "$TUNNEL_PID_FILE")" 2>/dev/null || true
    fi
    # 兜底：按命令特征清残留的 ssh 隧道进程，SIGTERM 无效则升级 SIGKILL
    pkill -f "ssh -N -R ${REMOTE_BIND_IP}:${REMOTE_PORT}" 2>/dev/null || true
    sleep 1
    pkill -9 -f "ssh -N -R ${REMOTE_BIND_IP}:${REMOTE_PORT}" 2>/dev/null || true
    rm -f "$TUNNEL_PID_FILE" "$STOP_FLAG"
    green "[tunnel] 已停止"
}

# ---------- 端到端验证 ----------
verify() {
    cyan "[verify] 从 ${SSH_HOST} 内网侧访问 ..."
    local code path
    path=$(access_path)
    code=$(ssh -o ConnectTimeout=15 -o BatchMode=yes "$SSH_HOST" \
        "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 10 http://${REMOTE_BIND_IP}:${REMOTE_PORT}${path}" 2>/dev/null || echo 000)
    if [[ "$code" == "200" || "$code" == "307" ]]; then
        green "[verify] 链路正常 (HTTP $code)"
    else
        red "[verify] 访问失败 (HTTP $code)，检查: $LOG_DIR/tunnel.log 与 $LOG_DIR/app.log"
    fi

    local web_code web_url
    web_url=$(web_phone_url)
    web_code=$(ssh -o ConnectTimeout=15 -o BatchMode=yes "$SSH_HOST" \
        "curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 10 '$web_url'" 2>/dev/null || echo 000)
    if [[ "$web_code" == "200" || "$web_code" == "307" ]]; then
        green "[verify] Web 链路正常 (HTTP $web_code)"
    else
        red "[verify] Web 访问失败 (HTTP $web_code)，检查: $LOG_DIR/web.log"
    fi
}

print_urls() {
    echo
    green "==================== 部署完成 ===================="
    echo "  家中局域网直连:       $(local_url)"
    echo "  外部 SSH 代理访问:    $(phone_url)"
    echo "  相机扫码唤起（可选）: $(flet_link)"
    echo "  家中 Web 直连:        $(web_local_url)"
    echo "  外部 Web 代理:        $(web_phone_url)"
    echo "----------------------------------------------------"
    echo "  前提: 手机 VPN 出口在 ${SSH_HOST}（${REMOTE_BIND_IP} 仅该机可达）"
    echo "  日志: ./debug_server.sh log app|web|tunnel"
    echo "===================================================="
    echo
}

# ---------- 子命令 ----------
cmd_start() {
    ensure_remote_nic
    start_app
    start_web
    start_tunnel
    verify
    print_urls
}

cmd_stop() {
    stop_app
    stop_web
    stop_tunnel
    green "全部停止"
}

cmd_restart_app() {
    stop_app
    stop_web
    start_app
    start_web
    verify
    green "应用已重启（隧道未动，手机端无需换地址）"
}

cmd_status() {
    echo "── debug 链路状态 ──────────────────────"
    if is_running "$APP_PID_FILE"; then
        green " app    运行中 (pid $(cat "$APP_PID_FILE"))  ${LOCAL_BIND_IP}:${LOCAL_PORT}$(access_path)"
    else
        red   " app    未运行"
    fi
    if is_running "$WEB_PID_FILE"; then
        green " web    运行中 (pid $(cat "$WEB_PID_FILE"))  ${LOCAL_BIND_IP}:${WEB_PORT}"
    else
        red   " web    未运行"
    fi
    if is_running "$TUNNEL_PID_FILE"; then
        green " tunnel 运行中 (pid $(cat "$TUNNEL_PID_FILE"))  ${SSH_HOST}:${REMOTE_BIND_IP}:${REMOTE_PORT}"
    else
        red   " tunnel 未运行"
    fi
    local listen
    listen=$(ssh -o ConnectTimeout=15 -o BatchMode=yes "$SSH_HOST" \
        "ss -tln 2>/dev/null | grep -c '${REMOTE_BIND_IP}:${REMOTE_PORT}'" 2>/dev/null || echo 0)
    if [[ "$listen" == "1" ]]; then
        green " 远端   ${REMOTE_BIND_IP}:${REMOTE_PORT} 监听中"
    else
        red   " 远端   ${REMOTE_BIND_IP}:${REMOTE_PORT} 未监听"
    fi
    echo
    echo "家中直连: $(local_url)"
    echo "外部代理: $(phone_url)"
    echo "家中 Web: $(web_local_url)"
    echo "外部 Web: $(web_phone_url)"
}

cmd_log() {
    local which="${1:-app}"
    if [[ "$which" == "tunnel" ]]; then
        tail -f "$LOG_DIR/tunnel.log"
    elif [[ "$which" == "web" ]]; then
        tail -f "$LOG_DIR/web.log"
    else
        tail -f "$LOG_DIR/app.log"
    fi
}

# ---------- 入口 ----------
SUBCMD="${1:-start}"
shift || true

POSITIONAL_ARGS=()
while (( $# )); do
    case "$1" in
        --new-uuid)
            rm -f "$UUID_FILE"
            echo "已轮换 UUID，手机端需使用新地址"
            shift
            ;;
        --secure)
            SECURE_ACCESS=1
            shift
            ;;
        --port)
            [[ $# -ge 2 ]] || { red "--port 缺少端口值"; exit 1; }
            LOCAL_PORT="$2"
            REMOTE_PORT="$2"
            shift 2
            ;;
        --port=*)
            LOCAL_PORT="${1#*=}"
            REMOTE_PORT="$LOCAL_PORT"
            shift
            ;;
        --web-port)
            [[ $# -ge 2 ]] || { red "--web-port 缺少端口值"; exit 1; }
            WEB_PORT="$2"
            shift 2
            ;;
        --web-port=*)
            WEB_PORT="${1#*=}"
            shift
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ ! "$LOCAL_PORT" =~ ^[0-9]+$ ]] || (( LOCAL_PORT < 1 || LOCAL_PORT > 65535 )); then
    red "无效端口: $LOCAL_PORT（应为 1-65535）"
    exit 1
fi
if [[ ! "$WEB_PORT" =~ ^[0-9]+$ ]] || (( WEB_PORT < 1 || WEB_PORT > 65535 )); then
    red "无效 Web 端口: $WEB_PORT（应为 1-65535）"
    exit 1
fi
if [[ "$SECURE_ACCESS" != "0" && "$SECURE_ACCESS" != "1" ]]; then
    red "DEBUG_SECURE_ACCESS 只能是 0 或 1"
    exit 1
fi
if [[ "$WEB_PORT" == "$REMOTE_PORT" ]]; then
    red "原生端口和 Web 端口不能相同: $WEB_PORT"
    exit 1
fi
if (( ${#POSITIONAL_ARGS[@]} )); then
    set -- "${POSITIONAL_ARGS[@]}"
else
    set --
fi

case "$SUBCMD" in
    start)        cmd_start ;;
    stop)         cmd_stop ;;
    restart)      cmd_stop; cmd_start ;;
    restart-app)  cmd_restart_app ;;
    status)       cmd_status ;;
    log)          cmd_log "$@" ;;
    *) echo "用法: $0 {start|stop|restart|restart-app|status|log [app|web|tunnel]} [--port PORT] [--web-port PORT] [--secure]"; exit 1 ;;
esac
