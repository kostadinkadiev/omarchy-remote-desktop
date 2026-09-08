# Remote Desktop 0.1.0

Share one existing Omarchy monitor over RDP with native shell controls, private
LAN/VPN binding, password-file authentication and a persistent certificate.

- One On/Off control remembers whether access resumes after desktop login.
- Share audio plays locally and remotely; settings preserve the On/Off choice.
- Connection-file export contains no password and works with RDP clients.
- Bar sizing keeps neighboring plugins visible; reconnect checks allow closed
  TCP sessions without accepting an occupied listening port.

Windows and Android: user-tested. Audio mirroring and logout/login: user-confirmed.
Mac: expected compatible through Microsoft Windows App, not tested with this
plugin. Android audio delay remains a known limitation.

Requires a compatible hypr-rdp backend; the included installer builds a fixed,
checksum-verified source snapshot. It asks for normal package-management privileges.
Runtime does not modify firewall, VPN, router or sudoers configuration.

See SECURITY.md and docs/RELEASE-REVIEW.md for security scope and validation limits.
