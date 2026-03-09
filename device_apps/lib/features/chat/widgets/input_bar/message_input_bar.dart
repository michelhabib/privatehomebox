import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../application/providers.dart';
import '../../../../core/errors/app_exception.dart';

class MessageInputBar extends ConsumerStatefulWidget {
  const MessageInputBar({super.key, required this.channelId});

  final String channelId;

  @override
  ConsumerState<MessageInputBar> createState() => _MessageInputBarState();
}

class _MessageInputBarState extends ConsumerState<MessageInputBar> {
  final _controller = TextEditingController();
  bool _hasText = false;

  @override
  void initState() {
    super.initState();
    _controller.addListener(() {
      final has = _controller.text.trim().isNotEmpty;
      if (has != _hasText) setState(() => _hasText = has);
    });
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _controller.clear();
    try {
      await ref.read(messageSendNotifierProvider.notifier).sendText(
            channelId: widget.channelId,
            text: text,
          );
    } on AppException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to send: ${e.message}'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Failed to send message'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final gatewayState = ref.watch(gatewayNotifierProvider);
    final isConnected = gatewayState is GatewayConnected;

    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
        decoration: BoxDecoration(
          color: cs.surface,
          border: Border(
            top: BorderSide(color: cs.outlineVariant, width: 0.5),
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: _controller,
                enabled: isConnected,
                maxLines: 5,
                minLines: 1,
                textInputAction: TextInputAction.newline,
                keyboardType: TextInputType.multiline,
                decoration: InputDecoration(
                  hintText: isConnected
                      ? 'Type a message…'
                      : 'Connecting to gateway…',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                  filled: true,
                  fillColor: cs.surfaceContainerHigh,
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 10,
                  ),
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(width: 8),
            AnimatedOpacity(
              opacity: _hasText && isConnected ? 1.0 : 0.5,
              duration: const Duration(milliseconds: 150),
              child: IconButton.filled(
                onPressed: (_hasText && isConnected) ? _send : null,
                icon: const Icon(Icons.send_rounded),
                style: IconButton.styleFrom(
                  backgroundColor: cs.primary,
                  foregroundColor: cs.onPrimary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}
