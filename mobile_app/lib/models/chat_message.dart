class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.body,
    required this.senderId,
    required this.timestamp,
    required this.isOutbound,
  });

  final String id;
  final String body;
  final String senderId;
  final DateTime timestamp;
  final bool isOutbound;
}
