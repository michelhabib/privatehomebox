import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../controllers/app_controller.dart';

class PairingScreen extends StatefulWidget {
  const PairingScreen({super.key});

  @override
  State<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends State<PairingScreen> {
  final TextEditingController _gatewayController =
      TextEditingController(text: 'ws://localhost:8765');
  final TextEditingController _pairingCodeController = TextEditingController();

  @override
  void dispose() {
    _gatewayController.dispose();
    _pairingCodeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppController>();
    final canSubmit = !app.busy &&
        _gatewayController.text.trim().isNotEmpty &&
        _pairingCodeController.text.trim().isNotEmpty;

    return Scaffold(
      appBar: AppBar(title: const Text('Pair device')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: <Widget>[
            Text(
              'Enter gateway URL and pairing code from `phbcli device add`.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _gatewayController,
              decoration: const InputDecoration(
                labelText: 'Gateway URL',
                border: OutlineInputBorder(),
                hintText: 'ws://192.168.1.100:8765',
              ),
              keyboardType: TextInputType.url,
              textInputAction: TextInputAction.next,
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _pairingCodeController,
              decoration: const InputDecoration(
                labelText: 'Pairing code',
                border: OutlineInputBorder(),
              ),
              keyboardType: TextInputType.number,
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: canSubmit
                  ? () async {
                      await context.read<AppController>().startPairing(
                            gatewayUrl: _gatewayController.text.trim(),
                            pairingCode: _pairingCodeController.text.trim(),
                          );
                    }
                  : null,
              child: app.busy
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Pair now'),
            ),
            if (app.error != null) ...<Widget>[
              const SizedBox(height: 12),
              Text(
                app.error!,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.error,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
