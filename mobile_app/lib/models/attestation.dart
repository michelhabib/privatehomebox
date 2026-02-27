class DeviceAttestation {
  const DeviceAttestation({
    required this.blob,
    required this.desktopSignature,
  });

  final String blob;
  final String desktopSignature;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'blob': blob,
      'desktop_signature': desktopSignature,
    };
  }

  static DeviceAttestation fromJson(Map<String, dynamic> json) {
    return DeviceAttestation(
      blob: (json['blob'] ?? '') as String,
      desktopSignature: (json['desktop_signature'] ?? '') as String,
    );
  }
}
