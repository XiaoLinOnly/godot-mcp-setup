# Godot MCP × Qoder 接入

让 Qoder Desktop 通过 MCP 操作本机 Godot 编辑器（场景、节点、脚本、文件系统等）。MCP 插件来自 [DaxianLee/godot-mcp](https://github.com/DaxianLee/godot-mcp)（v1.0.0）；本仓库只保存 Qoder 侧的 HTTP 接入配置、项目检查/探活脚本和实测说明，**不包含上游插件代码**。

链路：

```
Qoder Desktop → HTTP MCP (http://127.0.0.1:3000/mcp) → Godot 编辑器内 EditorPlugin
```

## 实测环境

| 项 | 版本 |
| --- | --- |
| OS | Windows 10/11 x64 |
| Godot | 4.7.2 stable（非 .NET 版） |
| godot-mcp 插件 | 1.0.0 |
| 传输 | HTTP，JSON-RPC 2.0，protocol `2024-11-05` |
| 工具数 | 74 |
| Qoder | Desktop，用户级 MCP |

已验证：编辑器运行时 HTTP 握手、`tools/list`（74 个工具）、`project_info` 返回项目信息。服务只在 Godot 编辑器进程活着时监听；编辑器一关，Qoder 里的 `godot` 连接就会失败，这是设计行为。

## 安装插件

上游没有 npm/PyPI 包，需要把插件目录放进项目：

```powershell
git clone https://github.com/DaxianLee/godot-mcp.git
New-Item -ItemType Directory -Force "D:\path\to\your-project\addons" | Out-Null
Copy-Item -Recurse .\godot-mcp\addons\godot_mcp "D:\path\to\your-project\addons\godot_mcp"
```

也可以从上游 Releases 下载压缩包，把 `addons/godot_mcp` 复制到项目根目录的 `addons/` 下。

启用插件二选一：

- 编辑器里 `Project → Project Settings → Plugins`，勾选 **Godot MCP Server**；
- 或在 `project.godot` 里加：

```ini
[editor_plugins]

enabled=PackedStringArray("res://addons/godot_mcp/plugin.cfg")
```

### 启动服务

插件默认 `auto_start=true`，启用后打开项目就会监听 `127.0.0.1:3000`。编辑器右侧会出现 **GodotMCP** 停靠面板，显示 endpoint、连接数和工具开关。

如果没起来：

1. 确认右侧 **GodotMCP** 面板里的服务开关是开的；
2. 确认端口 3000 没有被别的程序占用；
3. 改端口后要同步改 Qoder 的 URL。

插件设置保存在 `user://godot_mcp_settings.json`（Windows 即 `%APPDATA%\Godot\app_userdata\<项目名>\godot_mcp_settings.json`），相关默认值：

```json
{
  "port": 3000,
  "host": "127.0.0.1",
  "auto_start": true
}
```

## 注册到 Qoder

编辑 `%USERPROFILE%\.qoder-cn\settings.json`，在 `mcpServers` 下加入：

```json
"godot": {
  "type": "http",
  "url": "http://127.0.0.1:3000/mcp"
}
```

完整片段见 [`qoder/godot.mcp.json`](qoder/godot.mcp.json)。保存后重启 Qoder 或新开一个会话。

## 验证

```powershell
python scripts/probe_godot_mcp.py
```

预期输出（节选）：

```
ENDPOINT: http://127.0.0.1:3000/mcp
INIT: godot-mcp-server 1.0.0 (protocol 2024-11-05)
TOOL COUNT: 74
TOOLS: scene_management, scene_hierarchy, scene_run, node_query, node_lifecycle, project_info, ...
```

探活脚本需要 Python 3.8+（只用标准库）。

再真实读一次项目信息：

```powershell
python scripts/probe_godot_mcp.py --call project_info --args '{"action":"get_info"}'
```

项目侧还可以先跑检查脚本：

```powershell
powershell -ExecutionPolicy ByPass -File scripts/install.ps1 -ProjectPath "D:\path\to\your-project"
```

它会检查 `addons/godot_mcp/plugin.cfg`、`project.godot` 的 `[editor_plugins]` 是否启用、3000 是否在监听，并打印 Qoder 配置。

## 打开编辑器的正确命令

```powershell
& "C:\Program Files\Godot\Godot_v4.7.2-stable_win64.exe" -e --path "D:\path\to\your-project"
```

`-e` 是编辑器的关键；只给 `--path` 是**运行游戏**，不会加载 EditorPlugin，也就不会起 MCP 服务。

## 常见问题

| 现象 | 原因 / 处理 |
| --- | --- |
| Qoder 里 `godot` 连接失败 | 编辑器没开或插件没启用；服务只在编辑器进程内监听 |
| 编辑器开着但 3000 没监听 | 插件未启用、`auto_start` 被关、端口被改；看右侧 **GodotMCP** 面板 |
| 端口冲突 | 3000 被其他程序占用；在插件面板改端口，并同步改 Qoder 的 `url` |
| 改了 `project.godot` 不生效 | 关掉项目重新打开；编辑器启动时才加载插件 |
| 只想运行游戏却连不上 | `--path` 单独用是运行游戏；加 `-e` 才是编辑器 |
| Qoder 看不到工具 | 新开一个会话；MCP 工具在会话启动时加载 |
| 工具数少于 74 | 插件面板里禁用了部分工具，或版本不同 |

## 安全提示

该插件让模型直接改场景、节点和脚本。接入前先提交/备份项目；`host` 保持 `127.0.0.1`，不要改成 `0.0.0.0`，否则同网段任何人都能连。Qoder 会话里执行删除/覆盖操作前先确认。

## 卸载

在 `Project Settings → Plugins` 关闭 **Godot MCP Server**，删除项目里的 `addons/godot_mcp`，从 `settings.json` 删除 `godot` 条目。

## 许可与来源

本仓库的配置、脚本与文字为 MIT。MCP 插件来自 [DaxianLee/godot-mcp](https://github.com/DaxianLee/godot-mcp)，版权归 LIDAXIAN。上游使用自定义的 **Non-Commercial Use License**（仅限非商业用途；GitHub 识别为 Other / NOASSERTION），因此本仓库不分发其代码；商业使用、再分发前请自行取得授权。本项目与 Godot 基金会无关联。
