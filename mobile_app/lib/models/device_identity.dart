import 'attestation.dart';

class DeviceIdentity {
  const DeviceIdentity({
    required this.deviceId,
    required this.seedBase64,
    required this.publicKeyBase64,
    required this.gatewayUrl,
    this.desktopDeviceId,
    this.attestation,
  });

  final String deviceId;
  final String seedBase64;
  final String publicKeyBase64;
  final String gatewayUrl;
  final String? desktopDeviceId;
  final DeviceAttestation? attestation;

  DeviceIdentity copyWith({
    String? deviceId,
    String? seedBase64,
    String? publicKeyBase64,
    String? gatewayUrl,
    String? desktopDeviceId,
    DeviceAttestation? attestation,
  }) {
    return DeviceIdentity(
      deviceId: deviceId ?? this.deviceId,
      seedBase64: seedBase64 ?? this.seedBase64,
      publicKeyBase64: publicKeyBase64 ?? this.publicKeyBase64,
      gatewayUrl: gatewayUrl ?? this.gatewayUrl,
      desktopDeviceId: desktopDeviceId ?? this.desktopDeviceId,
      attestation: attestation ?? this.attestation,
    );
  }
}
