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
  「测试成功」 and a JSON tree containing the response. Save → row appears in list. Toggle → status
  flips 启用/禁用. Delete → row disappears. Each action calls a
  `/api/ext/custom_api/{test,save,list,toggle,delete}` route.
- **Dynamic handler registration:** saving/toggling/deleting triggers `plugin_manager.reload('custom_api')`.
  Watch the server log — it prints `[插件:custom_api] 加载完成 (N 个处理器)` and
  `🔄 插件热重载 custom_api`. Enabling one API → 1 处理器; disabling/deleting → 0.
- **broadcast (partial):** the page renders and 获取可用ID calls `/api/ext/broadcast/get_ids`,
  returning 「成功获取 N 个群聊和 M 个私聊」. With no recent message activity this is 0/0 — expected.

## What needs the user / a live session

- **broadcast real send** requires an active session in the message DB. The available-ID list only
  shows groups active in the last ~5 min and users in the last ~1 hr. To populate it, the user must
  send a message to the bot from QQ first (group @bot or DM).

## Gotchas / debugging

- **brotli / Accept-Encoding (IMPORTANT):** if a custom_api test fails with
  `网络错误: Expecting value: line 1 column 1 (char 0)` (a JSON decode error on an empty/garbled
  body), the likely cause is `Accept-Encoding: gzip, deflate, br` being sent while the Python env has
  **no `brotli`/`brotlicffi` library**. Cloudflare-backed APIs (e.g. `60s.viki.moe`) then return a
  brotli body that `requests` can't decode. Note the request headers come from BOTH `main.py`
  (`_DEFAULT_HEADERS`, used when the form headers box is empty) AND `page.html`
  (`showAddApiModal()` auto-fills the headers box with defaults on every 「添加API」, plus
  `fillDefaultHeaders()`). The form-filled headers OVERRIDE the backend default, so fixing only
  `main.py` is NOT enough — you must also remove `br` from `page.html`. Workarounds: drop `br` from
  the defaults, or install brotli in the env.
- **Reproducing a UI request via curl:** the `?token=admin` access_token is NOT a valid session for
  `/api/ext/...`; grab the real session token from the browser (`localStorage.getItem('elaina_token')`)
  and pass it as `?token=`. But beware: a plain curl with empty headers can PASS while the UI FAILS,
  because the UI auto-fills default headers — always mirror the exact form payload (including the
  auto-filled `headers`) when reproducing.
- Chinese text typed into some inputs via the computer tool may not register (IME); ASCII fields
  (regex/URL) work fine.
- After editing `page.html`, hard-refresh the browser (Ctrl+Shift+R) — it is served fresh from disk
  but the browser caches it.

## Devin Secrets Needed

- None required for custom_api + broadcast page/route tests.
- QQ bot `appid` + `secret` only needed for the real broadcast-send path (provided ad hoc by the user).
