---
name: testing-plugin-panels
description: Test the ElainaBot_v2 broadcast / custom_api plugin Web panels end-to-end. Use when verifying these (or similar register_page/register_route based) plugins after adapting them to ElainaBot_v2.
---

# Testing ElainaBot_v2 plugin Web panels

These plugins (`broadcast`, `custom_api`) are Web-panel plugins for the ElainaBot_v2 framework
(https://github.com/ElainaCore/ElainaBot_v2). To test them you run the framework locally with the
plugin directories copied into `plugins/`, then drive the panels through the Web UI.

## Run the framework locally

1. Clone `ElainaCore/ElainaBot_v2`; copy this repo's `broadcast/` and `custom_api/` into its `plugins/`.
2. Create `config/settings.yaml` with a known web token/password:
   ```yaml
   server:
     port: 15200
   web:
     access_token: "admin"
     admin_password: "admin"
   ```
3. (Optional, only needed for real message send) put bot credentials in `config/bot.yaml`
   (`appid` + `secret`). The bot then connects via WebSocket (`wss://api.sgroup.qq.com/websocket`).
4. Activate the framework venv and run `python main.py`. HTTP server starts on the configured port.
5. Open `http://localhost:<port>/web/?token=admin`. If a login page appears, enter the
   `admin_password` (default `admin`). The plugin pages show up in the left sidebar under 扩展页面
   (群发消息 = broadcast, 自定义API = custom_api), URLs like `/web/custom/<plugin_key>`.

The panel HTML is served from `/api/web-pages/<key>`; plugin endpoints live under `/api/ext/<plugin>/...`
and the token is passed via `?token=` query param (no need for a header from the iframe).

## What is fully testable without a live QQ session

- **custom_api (self-contained, recommended primary test):** add an API with a real public endpoint
  (e.g. regex `^getinfo$`, URL `https://httpbin.org/get`, type JSON), click 测试API → expect
  「测试成功」 and a JSON tree containing the response (`url=https://httpbin.org/get`). Save → row
  appears in list. Toggle → status flips 启用/禁用. Delete → row disappears. Each action calls a
  `/api/ext/custom_api/{test,save,list,toggle,delete}` route.
- **Dynamic handler registration:** saving/toggling/deleting triggers `plugin_manager.reload('custom_api')`.
  Watch the server log — it prints `[插件:custom_api] 加载完成 (N 个处理器)` and
  `🔄 插件热重载 custom_api`. Enabling one API → 1 处理器; disabling/deleting → 0. This is the
  strongest proof the regex trigger is wired to config.
- **broadcast (partial):** the page renders and 获取可用ID calls `/api/ext/broadcast/get_ids`,
  returning 「成功获取 N 个群聊和 M 个私聊」. With no recent message activity this is 0/0 — expected,
  not a bug.

## What needs the user / a live session

- **broadcast real send** requires an active session in the message DB. The available-ID list only
  shows groups active in the last ~5 min and users in the last ~1 hr (`direction='receive'` rows in
  `message.db`). To populate it, the user must send a message to the bot from QQ first (group @bot or
  DM). Only then can you select a target and actually 开始群发. Plan around this — don't expect the
  ID list to be populated on a fresh DB.

## Gotchas

- Chinese text typed into some inputs via the computer tool may not register (IME); ASCII fields
  (regex/URL) work fine. The 名称 field being empty after save is a test-harness input issue, not a
  plugin bug.
- The Devin GitHub integration may lack PR-comment permission (HTTP 403 on `gh pr comment`); deliver
  the test report/recording directly to the user instead.

## Devin Secrets Needed

- None required for custom_api + broadcast page/route tests.
- QQ bot `appid` + `secret` only needed for the real broadcast-send path (provided ad hoc by the user;
  not a stored secret).
