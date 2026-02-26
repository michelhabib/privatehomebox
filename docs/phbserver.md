# PHBServer/phbcli

## HKCU vs Task Scheduler

Using **HKCU Run** instead of **Task Scheduler** is like swapping a Swiss-army knife for a reliable pocket knife. It’s simpler and often works in locked-down domains, but you give up a bunch of control knobs.

What you lose (or change):

### Reliability and control

* **No built-in restart policy.**
  Task Scheduler can “restart on failure,” control retries, and enforce limits. HKCU Run just launches once at login. If your process crashes later, Windows won’t auto-relaunch it unless you build that into your app.

* **No “delayed start,” triggers, or conditions.**
  Scheduled Tasks can do: *on logon with delay*, *on idle*, *on network available*, *on AC power*, *wake the computer*, etc. HKCU Run is basically: “run this command at user logon, period.”

* **Less introspection.**
  With Task Scheduler you can query status, last run result, last run time, etc. HKCU Run doesn’t track any of that. You’ll need your own `status` (PID file, lock file, local socket ping, etc.).

### Security / execution context

* **Always runs as that user, interactive session.**
  That’s usually fine for a user-level agent. But if you ever wanted “run whether user is logged in or not” or “run as another account/SYSTEM,” HKCU Run can’t do that.

* **More vulnerable to user environment changes.**
  HKCU Run launches in the user logon environment. If your PATH, working directory assumptions, or dependencies are fragile, you’ll feel it more. (You can make it robust by launching a `.cmd` in a fixed user folder, like OpenClaw does.)

### Timing

* **Runs at logon only.**
  If the machine boots and nobody logs in, HKCU Run does nothing. (Task Scheduler can run at boot, or at logon, or both.)

### Policy / admin friction

* **Often allowed when Task Scheduler creation is blocked.**
  In domain environments, HKCU Run is frequently the path of least resistance. But some orgs also restrict registry Run keys; it depends on policy.

---

### What you *don’t* lose (and sometimes even gain)

* **No admin requirement** on most machines.
* **Simpler install/uninstall** (write/delete one registry value).
* **Fewer moving parts** (no task folder ACL drama).

---

### Best practice if you choose HKCU Run

If you go HKCU, I strongly recommend adding one of these in your app:

* a tiny **watchdog loop** (optional) that relaunches the worker if it dies, or
* a “single instance + self-heal” pattern:

  * on startup, create a lock (mutex/file/socket)
  * if already running, exit
  * optionally, periodically verify dependencies (port binding, etc.)

That gives you back most of the “restart on failure” value you’d otherwise get from Task Scheduler.

In a domain-joined Windows world, a solid pattern is:

* **Prefer Scheduled Task** (if install can elevate)
* **Fallback to HKCU Run** (if Task Scheduler registration is blocked or user refuses UAC)

It’s very “ship the product, not the perfect mechanism.”
