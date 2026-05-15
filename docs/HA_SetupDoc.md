# Getting Started: Home Assistant and Enhanced SunPower

If you landed here wondering whether Home Assistant is worth the effort, the short answer is yes. It gives you local control of your solar data without depending on a cloud service, and once it is running, it mostly takes care of itself. This guide walks you through the whole thing from picking hardware to having your SunPower system visible in your dashboard.

---

## Step 1: Pick Your Hardware

Home Assistant runs on a surprising range of hardware. Here are the most popular options:

**Home Assistant Green (easiest)**
The official Home Assistant appliance. Plug it in, connect it to your network, and follow the on-screen setup. Most people are up and running in under an hour. No configuration files, no flashing drives. If you want the path of least resistance, this is it.

**Raspberry Pi 5 with SSD**
A popular DIY option. Pair it with a 256 GB or larger SSD (not a microSD card, those wear out quickly) and you have a solid, low-power machine. The Pi 4 also works but the Pi 5 is noticeably faster.

**Mini PC / NUC / Old Laptop**
Any low-power x86 machine works well. Used NUCs and small form factor PCs are easy to find cheaply and make excellent Home Assistant hosts. An older laptop with the lid closed works too.

Whatever you choose, plan for it to run 24/7. Power consumption matters more than raw performance for this use case.

---

## Step 2: Install Home Assistant OS

Home Assistant OS (HAOS) is the recommended installation method. It includes everything you need, updates cleanly, and handles add-ons without any extra work on your part.

- **HA Green**: Comes with HAOS pre-installed. Just power it on.
- **Raspberry Pi**: Flash HAOS to your SSD using the Raspberry Pi Imager or Balena Etcher. Instructions are on the Home Assistant website.
- **x86 PC**: Download the HAOS disk image and write it to your drive. The Home Assistant documentation covers this step by step.

After first boot, open a browser on any computer on your network and go to `http://homeassistant.local:8123` to complete onboarding. If that address does not work, check your router for the IP address assigned to your HA device.

---

## Step 3: First Things to Set Up

Before you add any integrations, take care of these basics.

**Backups**
Set up automatic backups before you do anything else. Home Assistant can back up to Google Drive, OneDrive, Dropbox, a NAS, or a USB drive. Keep at least 30 days of backups. Losing a Home Assistant instance without a backup is painful.

Nabu Casa (the company behind HA) provides a cloud backup option, but it only keeps one backup file. Use it as a secondary option, not your only one.

**Remote Access**
If you want to access your dashboard away from home, Nabu Casa's Home Assistant Cloud subscription is the easiest and most secure option. It handles all the networking for you. If you go this route, use a strong, unique password and enable two-factor authentication.

**Updates**
Do not rush to install Home Assistant updates the day they release. Let them sit for a week or so while the community reports any issues. Core updates occasionally have breaking changes and a little patience saves a lot of headaches.

---

## Step 4: Set Up Your Network Properly

This step saves you a lot of trouble later.

**Assign a Static IP to Your HA Device**
Your router assigns IP addresses dynamically by default. If your HA device gets a new IP after a router reboot, your automations and bookmarks break. Set a DHCP reservation in your router so your HA device always gets the same IP address.

Every router is different. Search YouTube for "DHCP reservation" plus your router brand if you need help. The r/HomeNetworking subreddit (reddit.com/r/HomeNetworking) is also very helpful.

**Connect Your PVS Supervisor to WiFi**
Your SunPower PV Supervisor needs to be on your home WiFi network for this integration to work. Use the SunStrong app to connect it if you have not already. Once it is connected, your router will assign it an IP address, which you will need in a later step.

**Find Your PVS IP Address**
You need to know the IP address your router assigned to the PVS. A few ways to find it:

- Log in to your router's admin page and look at the DHCP client list. The PVS will show up with a name like "PVS6" or similar.
- Install **Fing** (free, iOS and Android) and run a network scan. It identifies devices on your network and shows their IP addresses.

Once you have the IP, set a DHCP reservation for the PVS too. If its IP changes, the integration will stop working until you update the configuration.

---

## Step 5: Install Essential Add-ons

Home Assistant add-ons extend what your instance can do. After setup, go to Settings, Add-ons to find these.

**HACS (Home Assistant Community Store)**
Required for installing Enhanced SunPower. HACS is a community-maintained store for integrations, frontend cards, and themes that are not in the official HA add-on store.

Install instructions: Settings, Add-ons, search HACS, or follow this short video walkthrough:
[HACS Install Video](https://www.youtube.com/watch?v=a4lSlN6EI04&t=6s)

You will need a free GitHub account during the HACS setup process. The video covers this.

**Advanced SSH and Web Terminal (optional but recommended)**
Lets you access a command line on your HA instance directly from the browser. Useful for troubleshooting and running scripts.

**Studio Code Server or File Editor (optional but recommended)**
Lets you view and edit Home Assistant configuration files directly in the browser. Handy when you need to make manual changes to configuration YAML.

---

## Step 6: Install Enhanced SunPower

Once HACS is installed, you are ready to add the Enhanced SunPower integration. Full installation and configuration instructions are in the README, including how to find your PVS password (it is the last 5 characters of your PVS serial number).

The README is at: [github.com/smcneece/ha-esunpower](https://github.com/smcneece/ha-esunpower)

---

## Getting Help

**Home Assistant Community**
The official forum at community.home-assistant.io is large and active. Most questions have already been answered there.

**Reddit**
r/homeassistant and r/SunPower are both helpful communities. Search before posting, but do not hesitate to ask if you cannot find an answer.

**YouTube**
Excellent resource for visual walkthroughs. "Home Assistant beginner" returns a lot of quality content if you want a guided tour of the interface.

**Enhanced SunPower Issues**
For bugs or questions specific to this integration, open an issue on GitHub at github.com/smcneece/ha-esunpower/issues.
