# phb-channel-echo

Echo channel plugin for Private Home Box — for development and integration testing.

Any outbound message sent to this channel is immediately reflected back as an inbound
message, prefixed with `[echo]`. Use it to verify the full plugin pipeline is working.

## Usage

```bash
# Install within the uv workspace (dev)
uv sync

# Register with phbcli
phbcli channel setup echo

# Run manually (phbcli starts it automatically on phbcli start)
phb-channel-echo --phb-ws ws://127.0.0.1:18081
```
