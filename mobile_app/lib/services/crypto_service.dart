import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:uuid/uuid.dart';

class GeneratedIdentity {
  const GeneratedIdentity({
    required this.deviceId,
    required this.seedBase64,
    required this.publicKeyBase64,
  });

  final String deviceId;
  final String seedBase64;
  final String publicKeyBase64;
}

class CryptoService {
  CryptoService() : _algorithm = Ed25519();

  final Ed25519 _algorithm;
  final Uuid _uuid = const Uuid();

  Future<GeneratedIdentity> generateIdentity() async {
    final seed = Uint8List.fromList(
      List<int>.generate(32, (_) => Random.secure().nextInt(256)),
    );
    final keyPair = await _algorithm.newKeyPairFromSeed(seed);
    final publicKey = await keyPair.extractPublicKey();
    return GeneratedIdentity(
      deviceId: 'phone-${_uuid.v4()}',
      seedBase64: base64Encode(seed),
      publicKeyBase64: base64Encode(publicKey.bytes),
    );
  }

  Future<String> signNonce(String seedBase64, String nonceHex) async {
    final seed = base64Decode(seedBase64);
    final keyPair = await _algorithm.newKeyPairFromSeed(seed);
    final nonce = _decodeHex(nonceHex);
    final signature = await _algorithm.sign(
      nonce,
      keyPair: keyPair,
    );
    return base64Encode(signature.bytes);
  }

  Uint8List _decodeHex(String hex) {
    final clean = hex.trim();
    if (clean.length.isOdd) {
      throw const FormatException('Invalid nonce hex');
    }
    final bytes = <int>[];
    for (var i = 0; i < clean.length; i += 2) {
      bytes.add(int.parse(clean.substring(i, i + 2), radix: 16));
    }
    return Uint8List.fromList(bytes);
  }
}
