import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../models/attestation.dart';
import '../models/device_identity.dart';

class StorageService {
  StorageService() : _storage = const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const String _kDeviceId = 'device_id';
  static const String _kSeed = 'seed_b64';
  static const String _kPublicKey = 'public_key_b64';
  static const String _kGatewayUrl = 'gateway_url';
  static const String _kDesktopDeviceId = 'desktop_device_id';
  static const String _kAttestationJson = 'device_attestation_json';

  Future<DeviceIdentity?> loadIdentity() async {
    final deviceId = await _storage.read(key: _kDeviceId);
    final seed = await _storage.read(key: _kSeed);
    final publicKey = await _storage.read(key: _kPublicKey);
    final gatewayUrl = await _storage.read(key: _kGatewayUrl);
    if (deviceId == null || seed == null || publicKey == null || gatewayUrl == null) {
      return null;
    }

    DeviceAttestation? attestation;
    final attestationRaw = await _storage.read(key: _kAttestationJson);
    if (attestationRaw != null) {
      try {
        final parsed = jsonDecode(attestationRaw) as Map<String, dynamic>;
        attestation = DeviceAttestation.fromJson(parsed);
      } catch (_) {
        attestation = null;
      }
    }

    return DeviceIdentity(
      deviceId: deviceId,
      seedBase64: seed,
      publicKeyBase64: publicKey,
      gatewayUrl: gatewayUrl,
      desktopDeviceId: await _storage.read(key: _kDesktopDeviceId),
      attestation: attestation,
    );
  }

  Future<void> saveIdentity(DeviceIdentity identity) async {
    await _storage.write(key: _kDeviceId, value: identity.deviceId);
    await _storage.write(key: _kSeed, value: identity.seedBase64);
    await _storage.write(key: _kPublicKey, value: identity.publicKeyBase64);
    await _storage.write(key: _kGatewayUrl, value: identity.gatewayUrl);
    if (identity.desktopDeviceId != null) {
      await _storage.write(key: _kDesktopDeviceId, value: identity.desktopDeviceId);
    }
    if (identity.attestation != null) {
      await _storage.write(
        key: _kAttestationJson,
        value: jsonEncode(identity.attestation!.toJson()),
      );
    }
  }

  Future<void> saveAttestation(DeviceAttestation attestation) async {
    await _storage.write(
      key: _kAttestationJson,
      value: jsonEncode(attestation.toJson()),
    );
  }

  Future<void> saveDesktopDeviceId(String desktopDeviceId) async {
    await _storage.write(key: _kDesktopDeviceId, value: desktopDeviceId);
  }

  Future<void> clearAll() async {
    await _storage.deleteAll();
  }
}
