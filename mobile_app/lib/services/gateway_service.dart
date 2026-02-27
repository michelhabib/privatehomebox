import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/attestation.dart';
import '../models/chat_message.dart';
import '../models/device_identity.dart';
import 'crypto_service.dart';

enum GatewayConnectionState {
  disconnected,
  connecting,
  authenticating,
  connected,
  pairing,
  error,
}

class PairingResult {
  const PairingResult({
    required this.attestation,
    this.desktopDeviceId,
  });

  final DeviceAttestation attestation;
  final String? desktopDeviceId;
}

class GatewayService {
  GatewayService(this._cryptoService);

  final CryptoService _cryptoService;
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _streamSub;

  final StreamController<ChatMessage> _messagesController =
      StreamController<ChatMessage>.broadcast();
  Stream<ChatMessage> get messages => _messagesController.stream;

  final StreamController<GatewayConnectionState> _stateController =
      StreamController<GatewayConnectionState>.broadcast();
  Stream<GatewayConnectionState> get states => _stateController.stream;

  GatewayConnectionState _state = GatewayConnectionState.disconnected;
  GatewayConnectionState get state => _state;

  DeviceIdentity? _identity;

  Future<void> connectAuthenticated(DeviceIdentity identity) async {
    await disconnect();
    _identity = identity;
    _setState(GatewayConnectionState.connecting);

    final channel = WebSocketChannel.connect(Uri.parse(identity.gatewayUrl));
    _channel = channel;
    final stream = channel.stream.asBroadcastStream();

    _setState(GatewayConnectionState.authenticating);
    final challenge = await _awaitChallenge(stream);
    final nonceSignature = await _cryptoService.signNonce(
      identity.seedBase64,
      challenge,
    );
    final attestation = identity.attestation;
    if (attestation == null) {
      throw StateError('Missing device attestation');
    }

    channel.sink.add(
      jsonEncode(
        <String, dynamic>{
          'type': 'auth_response',
          'auth_mode': 'device',
          'attestation': attestation.toJson(),
          'nonce_signature': nonceSignature,
        },
      ),
    );

    _streamSub = stream.listen(
      _handleIncomingMessage,
      onDone: () => _setState(GatewayConnectionState.disconnected),
      onError: (_) => _setState(GatewayConnectionState.error),
      cancelOnError: true,
    );
    _setState(GatewayConnectionState.connected);
  }

  Future<PairingResult> pairDevice({
    required DeviceIdentity identity,
    required String pairingCode,
  }) async {
    await disconnect();
    _identity = identity;
    _setState(GatewayConnectionState.pairing);
    final channel = WebSocketChannel.connect(Uri.parse(identity.gatewayUrl));
    _channel = channel;
    final stream = channel.stream.asBroadcastStream();

    final nonce = await _awaitChallenge(stream);
    final nonceSignature = await _cryptoService.signNonce(identity.seedBase64, nonce);
    channel.sink.add(
      jsonEncode(
        <String, dynamic>{
          'type': 'pairing_request',
          'pairing_code': pairingCode,
          'device_public_key': identity.publicKeyBase64,
          'device_id': identity.deviceId,
          'nonce_signature': nonceSignature,
        },
      ),
    );

    Map<String, dynamic>? response;
    try {
      response = await stream
          .map<Map<String, dynamic>?>((dynamic raw) => _toMap(raw))
          .firstWhere(
            (Map<String, dynamic>? map) =>
                map != null && map['type']?.toString() == 'pairing_response',
          )
          .timeout(const Duration(seconds: 40));
    } on StateError {
      throw StateError('Gateway closed connection before pairing response');
    } on TimeoutException {
      throw StateError('Timed out waiting for pairing response');
    }

    final status = response?['status']?.toString();
    if (status != 'approved') {
      throw StateError(response?['reason']?.toString() ?? 'Pairing was rejected');
    }
    final att = DeviceAttestation.fromJson(
      (response?['attestation'] as Map?)?.cast<String, dynamic>() ??
          <String, dynamic>{},
    );
    if (att.blob.isEmpty || att.desktopSignature.isEmpty) {
      throw StateError('Pairing did not return a valid attestation');
    }
    await disconnect();
    return PairingResult(
      attestation: att,
      desktopDeviceId: response?['desktop_device_id']?.toString(),
    );
  }

  Future<void> sendText({
    required String text,
    required String senderId,
    String? recipientId,
  }) async {
    final ws = _channel;
    if (ws == null || _state != GatewayConnectionState.connected) {
      throw StateError('Not connected');
    }
    final payload = <String, dynamic>{
      'id': DateTime.now().microsecondsSinceEpoch.toString(),
      'channel': 'devices',
      'direction': 'outbound',
      'sender_id': senderId,
      'recipient_id': recipientId,
      'content_type': 'text',
      'body': text,
      'metadata': <String, dynamic>{},
      'timestamp': DateTime.now().toUtc().toIso8601String(),
    };
    final envelope = <String, dynamic>{'payload': payload};
    if (recipientId != null && recipientId.isNotEmpty) {
      envelope['target_device_id'] = recipientId;
    }
    ws.sink.add(jsonEncode(envelope));
  }

  Future<void> disconnect() async {
    await _streamSub?.cancel();
    _streamSub = null;
    await _channel?.sink.close();
    _channel = null;
    _setState(GatewayConnectionState.disconnected);
  }

  void dispose() {
    _messagesController.close();
    _stateController.close();
  }

  Future<String> _awaitChallenge(Stream<dynamic> stream) async {
    Map<String, dynamic>? first;
    try {
      first = await stream
          .map<Map<String, dynamic>?>((dynamic raw) => _toMap(raw))
          .firstWhere(
            (Map<String, dynamic>? map) =>
                map != null && map['type']?.toString() == 'auth_challenge',
          )
          .timeout(const Duration(seconds: 20));
    } on StateError {
      throw StateError('Gateway closed connection before auth challenge');
    } on TimeoutException {
      throw StateError('Timed out waiting for auth challenge');
    }
    final nonce = first?['nonce']?.toString() ?? '';
    if (nonce.isEmpty) {
      throw StateError('Gateway challenge missing nonce');
    }
    return nonce;
  }

  Map<String, dynamic>? _toMap(dynamic raw) {
    if (raw is! String) {
      return null;
    }
    try {
      return (jsonDecode(raw) as Map).cast<String, dynamic>();
    } catch (_) {
      return null;
    }
  }

  void _handleIncomingMessage(dynamic raw) {
    final map = _toMap(raw);
    if (map == null) {
      return;
    }
    if (map['type']?.toString() == 'pairing_response') {
      return;
    }
    final payload = (map['payload'] as Map?)?.cast<String, dynamic>();
    if (payload == null) {
      return;
    }
    final body = payload['body']?.toString();
    if (body == null || body.isEmpty) {
      return;
    }
    final senderDeviceId = map['sender_device_id']?.toString() ??
        payload['sender_id']?.toString() ??
        'unknown';
    final message = ChatMessage(
      id: payload['id']?.toString() ?? DateTime.now().microsecondsSinceEpoch.toString(),
      body: body,
      senderId: senderDeviceId,
      timestamp: DateTime.tryParse(payload['timestamp']?.toString() ?? '')?.toUtc() ??
          DateTime.now().toUtc(),
      isOutbound: senderDeviceId == _identity?.deviceId,
    );
    _messagesController.add(message);
  }

  void _setState(GatewayConnectionState next) {
    _state = next;
    _stateController.add(next);
  }
}
