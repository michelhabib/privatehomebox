
# Daily Tasks

- Describe progressive Architecture in MintDocs, add Diagrams.
- add versioning.
- Log what really matters
- Move Docs to Mintdocs.
- Move all CLI commands to new tool design

# Refactoring

# Cleanup

# Add Features
- Resource Usage (CPU/Memory/Disk/Network/LLM$)
- security policy
- add browser tool
- install tools as plugins
- Add Memory
- Add RAG

# Iterations

- Draft Main Components
	- [x] CLI Setup, Start, Stop
	- [x] Gateway Relay
	- [x] Mobile/Web App
	- [x] RPC from Mobile to Server
	- [x] Fire Basic Agent and Response
	- [ ] Add Memory
	- [ ] Add Telegram/Whatsapp Channels

# Big Design Ideas

- Auto Test Cases.
- Auto Security Checks.
- Keep reviewing similar projects to improve security and usability.
- Easiest User Experience Setup.
- Win/Mac/Linux Support.
- Automate building process (local and release)

# Big Ideas

- Focus on 
	- Personal Assistance
	- Mental Wellness
	- Being a Loyal Friend/Visual Connection
	- Life Automation
- Leverage
	- Phone Connection
	- PC Connection
	- Home Connection
- Additional Help
	- Family Connection/Assistance
	- Home Assistance
- Values
	- Security and Control - Not yet another OpenClaw Clone
	- Warm/Friendly Connection
	- Accessibility
- Goals
	- Build in Public
	- Easy to Install
	- Many Common Features by default
	- Loosely coupled Interfaces (Plugin Architecture)

# Use Cases:
- Find information in my chats, files
- Bot to learn about me, my family, preferences, etc... and offer therapy
- Get web information on my behalf from social media, etc.. and send directly to me via chat
- Help me Organize, schedule and remind me of important things in my life
- Use my location, preferences, and my family's and kid's location and preferences for better life organiaztion. ex: kids are late, Kids are home, wife just left, stranger around home, provide info about places i am visiting.
- Access my home's cameras, wifi, iot, for better control and insight, notifications.

# Completed

- Initial Bootstrapping of Project.
  - phbcli
  - phbgateway
  - phb-channel-sdk (Devices Channel)
  - Flutter App Web
- phbcli Outbound Not Working
- Add xLogger Custom Logging module for better terminal tracking.
- introduce workspace concept for better organization of config files.
- introduce gateway instances concept for better organization of gateway config files.
- (tool-architecture) separate cli from functionality, and allow an api for the website.
- Refactor phbcli into organized folders - runtime/tools/commands/services/domain
 