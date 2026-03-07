# Main Idea

This project is intended for personal use. It builds an infrastructure for a team of agents/assistants to help the user manage his:
- Personal Tasks
- Personal Devices
- Life Automation
- Home Devices
- Family Devices

# Global Setup

## Root Node
root node is the desktop that has the main brain, running everything.
root node might have multiple workspaces (Production, Dev, Test). Each workspace run completely separate from the rest, different processes/subprocesses

## Device Nodes

These are different devices of different users connecting to the Root Node, they can chat with root node, or send information about the device, or requests from root node. It could be Mobile, Web or other desktops (win/mac/linux).


## Gateway

Gateway is the process instance that communicates between device nodes and root node workspaces, validating devices/pairing them, passing them through or denying them.
Gateway instances can run on the Root Node - as local gateways, or on the internet (VPS for example) - to allow paired/authenticated devices (outside the local Root Node Network) to connect to Root Node.
Multiple Gateway instances can be configured on the same Node/Server, but only one workspace can connect to one instance, it's a one to one connection only.
Gateway will later have pixel streaming for unreal engine.
Gateways use Websocket for communication, with crypto like auth - as described in [Device Auth](device-auth.md)

The ability to configure local or cloud gateway allow for flexible access from anywhere. We can keep it local and use VPN or Tailscale - not tested yet.

# Root Node Server

The phbcli - is a cli for creating and managing workspaces, channels, devices, etc...
the cli commands are also available as web interface for later use from http dashboard, as well as tools that can be controlled from AI Agent. [tool arch](../mintdocs/tools-architecture.mdx)

the service instance, running a single workspace, has the following components:

# server process

this is the main process that runs the workspace, it handles the http server, channel manager, communication manager, agent manager, and other services.
currently all of them run as asyncio coroutines, but later we might move some of them to threads for better performance.

## Channel Manager
currently named plugin manager, it spawns installed and enabled channels. It connects channels back to the server using a local websocket connection.
channel manager has the current core channel plugins:
- channel-device: for device communication, pairing, authentication, etc... it creates a websocket connection for devices to connect to. this is the same ip/port of the gateway instance.
channels are spawned as subprocesses.
a channel-plugin architecture is described in [channel-plugin-architecture.md](channel-plugin-architecture.md)
all new channels should be added as plugins, some of them will be core channels, some will be user plugins..

## Communication Manager
this is the central message router between channel manager and the application core, it handles inbound/outbound queuing and permission checks.
it is responsible for routing messages from channels to the application core, and from the application core to channels.
it is responsible for validating messages from channels, and sending them to the application core, and from the application core to channels.

## Agent Manager
this is the LLM worker that consumes text messages from the communication manager inbound queue, 
invokes a LangChain v1 create_agent instance, and pushes replies to the communication manager outbound queue.
This is still a very basic POC for the Agent Manager.

## HTTP Server
this is the http server that runs the workspace, it handles the http requests from the clients, and routes them to the appropriate services.
it currently handles the following endpoints:
- /status: to check the status of the workspace
- /channels: to list the channels and their status
- /tools: to list the tools and their status
- /invoke: to invoke a tool by name with a flat params dict

This is temporary for the POC, the most useful one is the invoke endpoint, which is used by the AI Agent to invoke tools - the same tools that are available to the CLI commands.


