import 'package:flutter/material.dart';

import '../services/gateway_service.dart';

class ConnectionIndicator extends StatelessWidget {
  const ConnectionIndicator({
    super.key,
    required this.state,
  });

  final GatewayConnectionState state;

  @override
  Widget build(BuildContext context) {
    final (Color color, String label) = switch (state) {
      GatewayConnectionState.connected => (Colors.green, 'Connected'),
      GatewayConnectionState.connecting => (Colors.orange, 'Connecting'),
      GatewayConnectionState.authenticating => (Colors.orange, 'Authenticating'),
      GatewayConnectionState.pairing => (Colors.blue, 'Pairing'),
      GatewayConnectionState.error => (Colors.red, 'Error'),
      GatewayConnectionState.disconnected => (Colors.grey, 'Disconnected'),
    };

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Icon(Icons.circle, size: 10, color: color),
        const SizedBox(width: 6),
        Text(label, style: Theme.of(context).textTheme.labelMedium),
      ],
    );
  }
}
