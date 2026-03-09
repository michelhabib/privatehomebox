import 'dart:async';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../../../core/constants/app_constants.dart';
import '../../../core/errors/app_exception.dart';
import '../../../core/utils/logger.dart';
import '../../../domain/models/identity/device_identity.dart';
import 'gateway_auth_handler.dart';
import 'gateway_inbound_frame.dart';
import 'gateway_protocol.dart';
import 'reconnect_policy.dart';

// ---------------------------------------------------------------------------
// Public connection update types
// ---------------------------------------------------------------------------

sealed class GatewayClientUpdate {}

class GatewayClientConnecting extends GatewayClientUpdate {}

class GatewayClientConnected extends GatewayClientUpdate {
  GatewayClientConnected(this.deviceId);
  final String deviceId;
}

class GatewayClientDisconnected extends GatewayClientUpdate {}

class GatewayClientError extends GatewayClientUpdate {
  GatewayClientError(this.message, {this.permanent = false});
  final String message;
  // Permanent errors (e.g. auth rejected) should not trigger reconnect.
  final bool permanent;
}

// ---------------------------------------------------------------------------
// GatewayClient
// ---------------------------------------------------------------------------

/// Raw WebSocket gateway connection.
///
/// Owns the reconnect loop and raw frame I/O.
/// Knows nothing about domain models beyond [DeviceIdentity] (needed for auth).
///
/// Usage:
///   final client = GatewayClient(...);
///   client.start(gatewayUrl: url, identity: identity);
///   client.updates  → stream of connection state changes
///   client.frames   → stream of decoded inbound messages
///   client.send(...)
///   await client.stop();
class GatewayClient {
  GatewayClient({
    required GatewayAuthHandler authHandler,
    required GatewayProtocol protocol,
    required ReconnectPolicy reconnectPolicy,
  })  : _authHandler = authHandler,
        _protocol = protocol,
        _reconnectPolicy = reconnectPolicy;

  final GatewayAuthHandler _authHandler;
  final GatewayProtocol _protocol;
  final ReconnectPolicy _reconnectPolicy;
  final _log = Logger.get('GatewayClient');

  final _updateController = StreamController<GatewayClientUpdate>.broadcast();
  final _frameController = StreamController<GatewayInboundFrame>.broadcast();

  Stream<GatewayClientUpdate> get updates => _updateController.stream;
  Stream<GatewayInboundFrame> get frames => _frameController.stream;

  WebSocketChannel? _channel;
  Completer<void>? _stopSignal;
  String? _connectedDeviceId;

  String? get connectedDeviceId => _connectedDeviceId;

  /// Starts the connection and reconnect loop.
  void start({required String gatewayUrl, required DeviceIdentity identity}) {
    _log.info('Starting gateway client', fields: {'url': gatewayUrl});
    _stopSignal = Completer<void>();
    _reconnectLoop(gatewayUrl, identity);
  }

  /// Stops the connection and reconnect loop.
  Future<void> stop() async {
    _log.info('Stopping gateway client');
    final signal = _stopSignal;
    if (signal != null && !signal.isCompleted) signal.complete();
    await _channel?.sink.close();
    _channel = null;
    _connectedDeviceId = null;
    _emit(GatewayClientDisconnected());
  }

  /// Sends a payload to all connected devices, or unicast to [targetDeviceId].
  void send(Map<String, dynamic> payload, {String? targetDeviceId}) {
    final ch = _channel;
    if (ch == null) {
      _log.warning('Send attempted while not connected — message dropped');
      return;
    }
    try {
      ch.sink.add(_protocol.encode(payload: payload, targetDeviceId: targetDeviceId));
    } catch (e) {
      _log.error('Send failed', error: e);
    }
  }

  Future<void> _reconnectLoop(String url, DeviceIdentity identity) async {
    final stopSignal = _stopSignal!;
    var attempt = 0;

    while (!stopSignal.isCompleted) {
      _emit(GatewayClientConnecting());
      try {
        await _connectOnce(url, identity, stopSignal);
        attempt = 0; // clean disconnect — reset backoff
      } on AuthException catch (e) {
        // Auth failures are permanent — attestation is invalid
        _log.error('Auth failed — stopping reconnect loop', error: e);
        _emit(GatewayClientError(e.message, permanent: true));
        return;
      } catch (e) {
        _log.warning('Connection lost', fields: {'attempt': attempt, 'error': '$e'});
      }

      if (stopSignal.isCompleted) break;

      _emit(GatewayClientDisconnected());
      final delay = _reconnectPolicy.delayFor(attempt++);
      _log.info('Reconnecting in', fields: {'seconds': delay.inSeconds, 'attempt': attempt});
      await Future.any([Future.delayed(delay), stopSignal.future]);
    }

    _emit(GatewayClientDisconnected());
  }

  Future<void> _connectOnce(
    String url,
    DeviceIdentity identity,
    Completer<void> stopSignal,
  ) async {
    final channel = WebSocketChannel.connect(Uri.parse(url));
    _channel = channel;

    // In web_socket_channel 3.x, channel.ready must be awaited. Without it,
    // a failed connection never sets up the stream listener, so sink.close()
    // in the finally block would hang forever (its done Future never completes).
    await channel.ready.timeout(
      AppConstants.authTimeout,
      onTimeout: () => throw const GatewayException('Connection timed out'),
    );

    final stream = channel.stream.asBroadcastStream();

    try {
      final authResult = await _authHandler.authenticate(
        stream: stream,
        sink: channel.sink,
        identity: identity,
      );
      _connectedDeviceId = authResult.deviceId;
      _emit(GatewayClientConnected(authResult.deviceId));

      // Run message loop until stream closes or stop() fires
      await Future.any([_runMessageLoop(stream, stopSignal), stopSignal.future]);
    } finally {
      _connectedDeviceId = null;
      // Do not await — if ready failed above the stream has no listener and
      // sink.done would never complete.
      channel.sink.close();
      _channel = null;
    }
  }

  Future<void> _runMessageLoop(Stream<dynamic> stream, Completer<void> stopSignal) async {
    await for (final raw in stream) {
      if (stopSignal.isCompleted) break;
      final frame = _protocol.decode(raw);
      if (frame != null) _frameController.add(frame);
    }
  }

  void _emit(GatewayClientUpdate update) {
    if (!_updateController.isClosed) _updateController.add(update);
  }

  /// Disposes stream controllers. Call only when the client will never be used again.
  void dispose() {
    _updateController.close();
    _frameController.close();
  }
}
