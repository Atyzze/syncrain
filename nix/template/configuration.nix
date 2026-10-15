# Your machine, with syncrain backdrop (Plasma 6, the rain as wallpaper, login and lock screen).
# Change what is marked; `nixos-option` and https://search.nixos.org/options for the rest.
{ pkgs, ... }:
{
  # CHANGE: the boot loader your machine uses now (copy it from /etc/nixos/configuration.nix).
  # syncrain never touches boot: it stays plain text until the rain says the machine is up.
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "backdrop";              # CHANGE
  time.timeZone = "Europe/Amsterdam";            # CHANGE
  i18n.defaultLocale = "en_US.UTF-8";
  services.xserver.xkb.layout = "us";            # the keyboard, on the login screen too

  # CHANGE: you
  users.users.alice = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" ];
    initialPassword = "change-me";               # then `passwd` once you are in
  };

  services.syncrain = {
    loginScreen.user = "alice";                  # CHANGE: offered first on the login screen
    # the look: open index.html from syncrain, press Settings, Save config.json next to this file
    # settings = ./config.json;
    # or options one by one (nix/options.nix in syncrain names them all):
    # theme = "nixos"; channel = "public"; snow = true;
  };

  environment.systemPackages = with pkgs; [ firefox git ];
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  system.stateVersion = "25.11";                 # the release you first installed; leave it after that
}
