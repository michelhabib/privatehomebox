Good. Now I have the full picture. Here is the consolidated, final architecture document.

---

# PHB Flutter App — Final Architecture Guidelines

> **No backward compatibility required** — this is a clean-slate build. The existing `device_apps` demo code is a reference only; the new app replaces it entirely.

---

## Locked Decisions

| # | Decision |
|---|---|
| 1 | Transport: WSS only. No E2E encryption for now. |
| 2 | Sync: online-first with a minimal outbox/retry for reliability. |
| 3 | Identity: one device can have multiple workspaces; each workspace has one active identity. |
| 4 | Message ordering: server timestamp is canonical; client timestamp is UI fallback only. |
| 5 | Notifications: local notifications first; push is a pluggable module added later. |
| 6 | Deep links: not required for production, but `go_router` URL structure is kept for dev/debug convenience. |
| 7 | i18n: not urgent, but the architecture must not block it (no hardcoded strings in widgets). |
| 8 | Local DB: messages and channels are cached locally in the app (Drift/SQLite). Server is the source of truth on refresh. |

---

## Core Concepts (Domain Language)

These terms must be used consistently everywhere — in code, comments, and AI prompts:

| Term | Meaning |
|---|---|
| **Workspace** | A named connection to one PHB gateway instance. A device can have multiple workspaces. |
| **Identity** | The cryptographic keypair + attestation for one workspace. |
| **Channel** | A topic or conversation thread. Channels are listed in the sidebar. |
| **Bot** | A personality/agent. A bot is NOT a channel — it is an entity that can be assigned to, or participate in, a channel. |
| **Session** | A conversation context within a channel. A channel can have multiple sessions (like threads). |
| **Message** | A single unit of communication in a channel/session. Has a type: text, image, video, voice, location, file. |
| **Gateway** | The WebSocket server the app connects to. |

---

## State Management: Riverpod v2 (with code generation)

**Why Riverpod over Provider:**
- Provider requires `BuildContext` to read state — Riverpod does not. This matters for services, repositories, and background tasks.
- Riverpod's `AsyncNotifier` handles loading/error/data states cleanly without boilerplate.
- Compile-time safety with `@riverpod` code generation — no string keys, no runtime errors.
- Providers are composable and testable in isolation.
- Scales to the complexity of this app (multiple workspaces, per-channel message streams, gateway lifecycle) without becoming a tangle.

**Rule:** One state approach across the entire app. Never mix Provider + Riverpod + Bloc.

---

## Architecture: Feature-First + 3-Layer

Each feature is a vertical slice. Inside each feature, three layers exist:

```
Presentation  →  Application  →  Domain  ←  Data
(widgets)        (providers)     (models,    (repositories,
                 (notifiers)      contracts)  remote, local)
```

**Dependency rule:**
- `domain` has zero Flutter or third-party dependencies. Pure Dart.
- `data` implements `domain` contracts (repository interfaces).
- `application` (Riverpod providers/notifiers) wires domain + data together.
- `presentation` reads providers only. Never touches repositories or services directly.

---

## Folder Structure

```
lib/
├── main.dart                    # ProviderScope, bootstrap only
├── app.dart                     # MaterialApp.router, theme, router config
│
├── core/                        # Shared primitives — no feature logic here
│   ├── constants/
│   │   ├── app_constants.dart
│   │   ├── route_names.dart
│   │   └── storage_keys.dart
│   ├── errors/
│   │   ├── app_exception.dart   # Sealed class hierarchy for typed errors
│   │   └── result.dart          # Result<T> type (success/failure)
│   ├── extensions/
│   │   ├── datetime_ext.dart
│   │   ├── string_ext.dart
│   │   └── context_ext.dart     # theme/size helpers on BuildContext
│   ├── utils/
│   │   ├── logger.dart          # Structured logging, redacts sensitive fields
│   │   └── platform_utils.dart  # kIsWeb, Platform checks, screen size helpers
│   └── ui/                      # Design system / UI kit
│       ├── atoms/               # Smallest indivisible widgets
│       │   ├── phb_avatar.dart
│       │   ├── phb_badge.dart
│       │   ├── status_dot.dart
│       │   └── loading_indicator.dart
│       ├── molecules/           # Composed from atoms
│       │   ├── connection_banner.dart
│       │   ├── error_snackbar.dart
│       │   └── confirmation_dialog.dart
│       └── theme/
│           ├── app_theme.dart       # Light + dark ThemeData (flex_color_scheme)
│           ├── app_colors.dart
│           └── app_text_styles.dart
│
├── config/
│   └── router/
│       ├── app_router.dart          # go_router definition, all routes
│       └── route_guards.dart        # Auth guard, lock guard, workspace guard
│
├── platform/                    # Platform-specific adapters behind interfaces
│   ├── biometrics/
│   │   ├── biometric_service.dart           # abstract interface
│   │   ├── biometric_service_mobile.dart
│   │   └── biometric_service_stub.dart      # web/desktop fallback
│   ├── notifications/
│   │   ├── notification_service.dart        # abstract interface
│   │   ├── notification_service_mobile.dart
│   │   └── notification_service_web.dart
│   ├── media/
│   │   ├── media_service.dart               # abstract interface
│   │   └── media_service_impl.dart
│   └── storage/
│       └── secure_storage_service.dart      # wraps flutter_secure_storage
│
├── data/                        # Data layer — no UI here
│   ├── local/
│   │   ├── database/
│   │   │   ├── app_database.dart            # Drift DB definition
│   │   │   ├── tables/                      # Drift table definitions (app-side only)
│   │   │   │   ├── messages_table.dart
│   │   │   │   ├── channels_table.dart
│   │   │   │   └── sessions_table.dart
│   │   │   └── daos/
│   │   │       ├── messages_dao.dart
│   │   │       ├── channels_dao.dart
│   │   │       └── sessions_dao.dart
│   │   └── cache/
│   │       └── workspace_cache.dart
│   ├── remote/
│   │   ├── gateway/
│   │   │   ├── gateway_client.dart          # Raw WSS connection, reconnect loop, heartbeat
│   │   │   ├── gateway_protocol.dart        # Frame serialization/deserialization
│   │   │   ├── gateway_auth_handler.dart    # Challenge/response, pairing flow
│   │   │   └── reconnect_policy.dart        # Exponential backoff config
│   │   └── http/
│   │       └── api_client.dart              # For any REST endpoints
│   └── repositories/
│       ├── auth_repository_impl.dart
│       ├── workspace_repository_impl.dart
│       ├── channel_repository_impl.dart
│       ├── message_repository_impl.dart
│       ├── session_repository_impl.dart
│       └── settings_repository_impl.dart
│
├── domain/                      # Pure Dart — zero Flutter dependency
│   ├── models/
│   │   ├── workspace/
│   │   │   └── workspace.dart               # freezed
│   │   ├── identity/
│   │   │   ├── device_identity.dart         # freezed
│   │   │   └── attestation.dart             # freezed
│   │   ├── channel/
│   │   │   ├── channel.dart                 # freezed
│   │   │   └── channel_type.dart            # enum: direct, group, topic
│   │   ├── bot/
│   │   │   └── bot.dart                     # freezed — separate from channel
│   │   ├── message/
│   │   │   ├── message.dart                 # freezed
│   │   │   ├── message_type.dart            # enum: text, image, video, voice, location, file
│   │   │   ├── message_status.dart          # enum: sending, sent, delivered, read, failed
│   │   │   └── message_content.dart         # sealed union per type
│   │   └── session/
│   │       └── conversation_session.dart    # freezed
│   ├── repositories/                        # Contracts (abstract classes only)
│   │   ├── auth_repository.dart
│   │   ├── workspace_repository.dart
│   │   ├── channel_repository.dart
│   │   ├── message_repository.dart
│   │   ├── session_repository.dart
│   │   └── settings_repository.dart
│   └── services/                            # Pure business logic
│       ├── crypto_service.dart
│       ├── pairing_service.dart
│       └── outbox_service.dart              # Retry logic for failed sends
│
├── application/                 # Riverpod providers and notifiers
│   ├── providers.dart           # Central barrel: all top-level provider declarations
│   ├── auth/
│   │   ├── auth_notifier.dart           # AsyncNotifier — pairing, identity lifecycle
│   │   └── auth_state.dart              # freezed state
│   ├── lock/
│   │   ├── lock_notifier.dart
│   │   └── lock_state.dart
│   ├── workspace/
│   │   ├── workspace_notifier.dart
│   │   └── active_workspace_provider.dart
│   ├── gateway/
│   │   ├── gateway_notifier.dart        # Connection lifecycle, reconnect
│   │   └── gateway_state.dart           # freezed: disconnected/connecting/connected/error
│   ├── channels/
│   │   ├── channels_notifier.dart       # Channel list for active workspace
│   │   └── channel_detail_provider.dart # Single channel by id
│   ├── messages/
│   │   ├── messages_provider.dart       # Stream<List<Message>> per channel
│   │   ├── message_send_notifier.dart   # Handles send + outbox
│   │   └── message_input_provider.dart  # Draft text, attachment state
│   ├── sessions/
│   │   └── sessions_provider.dart
│   ├── bots/
│   │   └── bots_provider.dart
│   ├── settings/
│   │   └── settings_notifier.dart
│   └── notifications/
│       └── notification_notifier.dart
│
└── features/                    # Presentation layer — screens and widgets
    ├── shell/
    │   ├── app_shell.dart               # ShellRoute widget (nav rail + bottom nav adaptive)
    │   └── nav_destinations.dart
    │
    ├── onboarding/
    │   ├── onboarding_screen.dart
    │   └── widgets/
    │       ├── qr_scanner_widget.dart
    │       ├── pairing_code_form.dart
    │       └── gateway_url_field.dart
    │
    ├── lock/
    │   ├── lock_screen.dart
    │   └── widgets/
    │       ├── biometric_prompt.dart
    │       ├── pin_pad.dart
    │       └── pattern_lock_widget.dart
    │
    ├── workspaces/
    │   ├── workspace_list_screen.dart
    │   └── widgets/
    │       └── workspace_tile.dart
    │
    ├── channels/
    │   ├── channel_list_screen.dart
    │   ├── add_channel_screen.dart
    │   └── widgets/
    │       ├── channel_list_tile.dart
    │       ├── channel_avatar.dart
    │       └── unread_badge.dart
    │
    ├── chat/
    │   ├── chat_screen.dart
    │   ├── chat_app_bar.dart
    │   └── widgets/
    │       ├── message_list.dart
    │       ├── message_bubble/
    │       │   ├── message_bubble.dart        # Dispatcher — switch on MessageType
    │       │   ├── text_bubble.dart
    │       │   ├── image_bubble.dart
    │       │   ├── video_bubble.dart
    │       │   ├── voice_bubble.dart
    │       │   ├── location_bubble.dart
    │       │   └── reply_preview.dart
    │       ├── input_bar/
    │       │   ├── message_input_bar.dart
    │       │   ├── attachment_picker.dart
    │       │   └── voice_recorder_button.dart
    │       └── message_context_menu.dart      # Forward, reply, copy actions
    │
    ├── sessions/
    │   ├── session_list_screen.dart
    │   └── widgets/
    │       └── session_tile.dart
    │
    ├── bots/
    │   ├── bot_list_screen.dart
    │   ├── create_bot_screen.dart
    │   ├── bot_webview_screen.dart            # WebView for bot UI
    │   ├── pixel_stream_screen.dart           # Unreal pixel streaming
    │   └── widgets/
    │       └── bot_tile.dart
    │
    ├── notifications/
    │   └── notification_settings_screen.dart
    │
    └── settings/
        ├── settings_screen.dart
        └── widgets/
            ├── theme_toggle.dart
            ├── security_settings_tile.dart
            └── gateway_settings_tile.dart
```

---

## Routing Structure

```
/                                → redirect: auth guard → lock guard → /app/channels
/onboarding                      → OnboardingScreen
/lock                            → LockScreen
/workspaces                      → WorkspaceListScreen
/app  (StatefulShellRoute)       → AppShell
  /app/channels                  → ChannelListScreen
  /app/channels/:channelId       → ChatScreen
  /app/channels/:channelId/sessions/:sessionId  → SessionChatScreen
  /app/bots                      → BotListScreen
  /app/bots/:botId               → BotWebViewScreen
  /app/bots/:botId/stream        → PixelStreamScreen
  /app/settings                  → SettingsScreen
```

On narrow screens (mobile): channels list and chat are stacked (push navigation).
On wide screens (tablet/desktop/web): `StatefulShellRoute` renders both panels side-by-side in a `Row` inside `AppShell`.

---

## Key Implementation Rules

### Models
- Every domain model uses `freezed`. No mutable model classes anywhere.
- JSON serialization lives in `data/` DTOs, not domain models. A mapper converts DTO → domain model.
- Never pass raw `Map<String, dynamic>` outside the `data/` layer.

### Widgets
- Screens are thin: they read providers and pass data down to child widgets.
- No business logic in widgets. No repository calls from widgets.
- No `if/else` chains dispatching message types in one widget — use `switch` in a dispatcher widget that delegates to typed sub-widgets.
- Strings are never hardcoded in widgets. Use a constants file or ARB files (i18n-ready from day one).
- Split any widget that exceeds ~80 lines into smaller named widgets.

### Gateway / WebSocket
- `GatewayClient` owns the raw connection, reconnect loop, and heartbeat. It knows nothing about domain models.
- `GatewayProtocol` handles frame parsing. It converts raw JSON to typed DTOs.
- `GatewayAuthHandler` handles the challenge/response and pairing flow.
- `GatewayNotifier` (Riverpod) owns the connection lifecycle and exposes state to the UI.
- `MessageRepository` subscribes to the gateway stream and writes to the local Drift DB.
- The UI reads from the local DB stream — it never reads directly from the WebSocket.

### Outbox Pattern
- When a message send fails (no connection), it goes into a local outbox table.
- `OutboxService` retries on reconnect.
- Message status in the UI reflects: `sending → sent → delivered → read` or `failed`.

### Platform Abstraction
- Anything that behaves differently on Android vs web vs iOS vs desktop lives in `platform/` behind an abstract interface.
- Riverpod providers in `application/` instantiate the correct platform implementation.
- Features never import from `platform/` directly — they go through the provider.

### Adaptive Layout
- `AppShell` detects screen width and renders either a `NavigationRail` (wide) or `NavigationBar` (narrow).
- The split-pane (channel list + chat) is implemented inside `StatefulShellRoute` — on wide screens both branches are visible simultaneously.
- A single `AdaptiveLayout.isWide(context)` utility (based on `MediaQuery.sizeOf`) is the single source of truth for breakpoints.

### Theming
- `AppTheme` provides both light and dark `ThemeData` using `flex_color_scheme`.
- No hardcoded colors or text styles in widgets — always use `Theme.of(context)` or named tokens from `app_colors.dart`.
- Theme mode is persisted in `SettingsRepository` and restored on startup.

---

## Packages (Recommended)

```yaml
dependencies:
  # State
  flutter_riverpod: ^2.x
  riverpod_annotation: ^2.x

  # Navigation
  go_router: ^14.x

  # Models
  freezed_annotation: ^2.x
  json_annotation: ^4.x

  # Local DB
  drift: ^2.x
  sqlite3_flutter_libs: ^0.x

  # Theming
  flex_color_scheme: ^8.x

  # Secure storage (already present)
  flutter_secure_storage: ^9.x

  # WebSocket (already present)
  web_socket_channel: ^3.x

  # Crypto (already present)
  cryptography: ^2.x

  # Biometrics
  local_auth: ^2.x

  # QR scanning
  mobile_scanner: ^6.x

  # Media
  image_picker: ^1.x
  file_picker: ^8.x

  # Notifications
  flutter_local_notifications: ^18.x

  # WebView
  webview_flutter: ^4.x

dev_dependencies:
  build_runner: ^2.x
  freezed: ^2.x
  json_serializable: ^6.x
  riverpod_generator: ^2.x
  drift_dev: ^2.x
```

---

## AI Coding Guardrails (use these verbatim in prompts)

1. "Implement by feature slice. Each feature has its own folder under `features/` for presentation and `application/` for state."
2. "Respect the 3-layer boundary: `features/` → `application/` → `domain/` ← `data/`. No layer may skip a level."
3. "Do not place business logic in widgets. Widgets read providers and render data."
4. "Do not access the gateway, database, or any service directly from a widget or screen."
5. "No raw `Map<String, dynamic>` outside `data/`. All data crossing the data/domain boundary must be a typed, freezed model."
6. "Every new feature requires: a freezed domain model, a repository contract in `domain/repositories/`, an implementation in `data/repositories/`, and a Riverpod notifier in `application/`."
7. "All platform-specific behavior (biometrics, notifications, file system, WebView) must be behind an abstract interface in `platform/`."
8. "No hardcoded strings in widgets. Use constants or ARB keys."
9. "No hardcoded colors or text styles in widgets. Use `Theme.of(context)` tokens."
10. "The gateway connection lifecycle lives in `GatewayNotifier`. The UI reads message data from the local DB stream via `MessageRepository`, not from the WebSocket directly."
11. "Adaptive layout breakpoints use `AdaptiveLayout.isWide(context)` only. No inline `MediaQuery` width checks scattered across widgets."
12. "A Bot is not a Channel. They are separate domain models with separate providers and separate screens."
13. "Message bubble rendering uses a dispatcher widget that switches on `MessageType` and delegates to a typed sub-widget. No monolithic bubble widget."
14. "State management is Riverpod v2 with code generation (`@riverpod`). Do not introduce Provider, Bloc, or GetX anywhere."

---

## Build Order (Feature by Feature)

| Phase | Features |
|---|---|
| 1 — Foundation | Folder structure, theme, router, AppShell (adaptive layout), core utilities |
| 2 — Identity | Onboarding (QR + pairing code), crypto, identity storage, workspace model |
| 3 — Lock | Biometric/PIN lock screen, lock guard in router |
| 4 — Gateway | GatewayClient, protocol, auth handler, reconnect, GatewayNotifier |
| 5 — Channels | Channel list, local DB, channel repository, channel list screen |
| 6 — Chat | Message model, MessageRepository (DB + gateway sync), chat screen, text bubble, input bar |
| 7 — Rich messages | Image, voice, video, location, file bubbles; attachment picker |
| 8 — Reply/Forward | Reply preview, forward action, message context menu |
| 9 — Bots | Bot model, bot list, bot assignment to channel, bot WebView screen |
| 10 — Sessions | Session model, session list, session chat |
| 11 — Pixel streaming | PixelStreamScreen with WebView + JS bridge |
| 12 — Notifications | Local notification service, notification on incoming message |
| 13 — Settings | Theme toggle, security settings, gateway settings |
| 14 — Multi-workspace | Workspace switcher, per-workspace identity, workspace-scoped providers |
| 15 — i18n | ARB files, `flutter_localizations`, string extraction |

---

This document is self-contained and can be handed to any coding AI as the authoritative reference for every implementation decision. Each phase in the build order is independent enough to be implemented in a single focused session.