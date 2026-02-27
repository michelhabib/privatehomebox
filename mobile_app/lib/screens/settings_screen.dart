import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../controllers/app_controller.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppController>();
    final identity = app.identity;
    final deviceId = identity?.deviceId ?? 'Unknown';
    final gateway = identity?.gatewayUrl ?? 'Unknown';
    final desktop = identity?.desktopDeviceId ?? '(broadcast)';

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: <Widget>[
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Device ID'),
            subtitle: Text(deviceId),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Gateway URL'),
            subtitle: Text(gateway),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Desktop device target'),
            subtitle: Text(desktop),
          ),
          const SizedBox(height: 20),
          OutlinedButton.icon(
            onPressed: () async {
              await context.read<AppController>().reconnect();
            },
            icon: const Icon(Icons.refresh),
            label: const Text('Reconnect'),
          ),
          const SizedBox(height: 8),
          FilledButton.tonalIcon(
            onPressed: () async {
              await context.read<AppController>().unpair();
              if (context.mounted) {
                Navigator.of(context).popUntil((Route<dynamic> route) => route.isFirst);
              }
            },
            icon: const Icon(Icons.link_off),
            label: const Text('Unpair this device'),
          ),
        ],
      ),
    );
  }
}
