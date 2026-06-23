# ElainaBot_v2plugins

适配 [ElainaBot_v2](https://github.com/ElainaCore/ElainaBot_v2) 框架的插件集合。

插件已按照 [PLUGIN_DEVELOPMENT.md](https://github.com/ElainaCore/ElainaBot_v2/blob/main/PLUGIN_DEVELOPMENT.md)
的装饰器规范从旧版（基于 `core.plugin.PluginManager.Plugin` 的类式插件）适配到 v2 框架。

## 插件列表

| 目录 | 名称 | 说明 |
| --- | --- | --- |
| [`broadcast/`](broadcast) | 群发消息 | Web 面板批量向群聊/私聊主动推送消息（文本/Markdown/模板Markdown/图片/语音/视频/ARK）。 |
| [`custom_api/`](custom_api) | 自定义API | Web 面板配置正则触发的自定义 HTTP API 调用，支持 JSON 路径提取、消息模板与多种回复类型。 |

> 旧版 v1 源码已移动到 [`legacy_v1/`](legacy_v1)，仅作参考，无法在 v2 框架中直接运行。

## 安装

将所需插件目录复制到 ElainaBot_v2 的 `plugins/` 目录下即可（框架会自动加载并支持热重载）：

```bash
# 在 ElainaBot_v2 项目根目录下
cp -r /path/to/ElainaBot_v2plugins/broadcast   plugins/
cp -r /path/to/ElainaBot_v2plugins/custom_api  plugins/
```

启动框架后，在 Web 面板左侧菜单即可看到「群发消息」「自定义API」两个页面。

## 适配要点

两个插件均为「Web 面板型」插件，适配过程中主要的框架差异：

- **页面与路由**：旧版的 `get_web_routes()` / `render_page()` 改为 v2 的
  `register_page(...)` 注册自定义页面、`@register_route('METHOD', '/api/ext/...')`
  注册 HTTP 接口。页面 HTML 独立为 `page.html`，由框架以 iframe 形式加载，
  鉴权 token 通过 URL 的 `?token=` 传入，前端请求 `/api/ext/<plugin>/<action>` 时附带。
- **消息处理器**：旧版的 `get_regex_handlers()` 改为 `@handler(pattern, ...)` 装饰器。
  `custom_api` 因为需要按用户配置动态注册任意数量的处理器，改为在模块导入时按配置
  循环调用 `@handler` 注册；配置在面板中变更后调用 `plugin_manager.reload()` 重新导入即可生效。
- **主动推送 / 回复**：旧版的模拟 `MessageEvent` 改为：群发用 `sender.send_to_group` /
  `sender.send_to_user`（及 `reply_image/voice/video` 配合 `target_group_id/target_user_id`
  主动推送媒体）；`custom_api` 在处理器内用 `event.reply* / event.reply_image` 等代理方法回复。
- **可用 ID 来源**：旧版从 MySQL 日志库查询活跃会话，改为读取 v2 框架自带的 SQLite
  消息日志（`message.db`，`direction='receive'`），筛选近期活跃的群/私聊（群 5 分钟、私聊 1 小时窗口）。
- **数据存储**：备注、API 配置等改为存放在各插件目录的 `data/` 子目录下的 JSON 文件。
